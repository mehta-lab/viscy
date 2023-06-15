import logging
import os
import tempfile
from typing import Any, Callable, Iterable, Literal, TypedDict, Union

import numpy as np
import torch
import zarr
from iohub.ngff import ImageArray, Position, open_ome_zarr
from lightning.pytorch import LightningDataModule
from monai.data import set_track_meta
from monai.transforms import (
    CenterSpatialCropd,
    Compose,
    InvertibleTransform,
    MapTransform,
    RandAdjustContrastd,
    RandAffined,
    RandGaussianSmoothd,
    RandWeightedCropd,
)
from numpy.typing import NDArray
from torch.utils.data import DataLoader, Dataset


class ChannelMap(TypedDict, total=False):
    source: str
    # optional
    target: str


class Sample(TypedDict, total=False):
    index: tuple[str, int, int]
    source: torch.Tensor
    # optional
    target: torch.Tensor


class NormalizeSampled(MapTransform, InvertibleTransform):
    """Dictionary transform to only normalize target (fluorescence) channel.

    :param Union[str, Iterable[str]] keys: keys to normalize
    :param Plate plate: NGFF HCS plate object
    :param ChannelMap channels: source and target channel names
    """

    def __init__(
        self,
        keys: Union[str, Iterable[str]],
        norm_meta: dict[str, str],
        channels: ChannelMap,
    ) -> None:
        if set(keys) > channels.keys():
            raise KeyError(f"Keys to transform ({keys}) not in {channels.keys()}")
        super().__init__(keys, allow_missing_keys=False)
        self.norm_meta = norm_meta
        self.channels = channels

    def _stat(self, key: str) -> dict:
        return self.norm_meta[self.channels[key]]["dataset_statistics"]

    def __call__(self, data: Sample) -> Sample:
        d = dict(data)
        for key in self.keys:
            d[key] = (d[key] - self._stat(key)["median"]) / self._stat(key)["iqr"]
        return d

    def inverse(self, data: Sample) -> Sample:
        d = dict(data)
        for key in self.keys:
            d[key] = (d[key] * self._stat(key)["iqr"]) + self._stat(key)["median"]


class SlidingWindowDataset(Dataset):
    """Torch dataset where each element is a window of
    (C, Z, Y, X) where C=2 (source and target) and Z is ``z_window_size``.

    :param list[Position] positions: FOVs to include in dataset
    :param ChannelMap channels: source and target channel names,
        e.g. ``{'source': 'Phase', 'target': 'Nuclei}``
    :param int z_window_size: Z window size of the 2.5D U-Net, 1 for 2D
    :param Callable[[Sample], Sample] transform: a callable that transforms data,
        defaults to None
    """

    def __init__(
        self,
        positions: list[Position],
        channels: ChannelMap,
        z_window_size: int,
        transform: Callable[[Sample], Sample] = None,
    ) -> None:
        super().__init__()
        self.positions = positions
        self.source_ch_idx = positions[0].get_channel_index(channels["source"])
        self.target_ch_idx = (
            positions[0].get_channel_index(channels["target"])
            if "target" in channels
            else None
        )
        self.z_window_size = z_window_size
        self.transform = transform
        self._get_windows()

    def _get_windows(self) -> None:
        w = 0
        self.window_keys = []
        self.window_arrays = []
        for fov in self.positions:
            img_arr = fov["0"]
            ts = img_arr.frames
            zs = img_arr.slices - self.z_window_size + 1
            w += ts * zs
            self.window_keys.append(w)
            self.window_arrays.append(img_arr)
        self._max_window = w

    def _find_window(self, index: int) -> tuple[int, int]:
        window_idx = sorted(self.window_keys + [index + 1]).index(index + 1)
        w = self.window_keys[window_idx]
        tz = index - self.window_keys[window_idx - 1] if window_idx > 0 else index
        return self.window_arrays[self.window_keys.index(w)], tz

    def _read_img_window(
        self, img: Union[ImageArray, NDArray], ch_idx: int, tz: int
    ) -> torch.Tensor:
        zs = img.shape[-3] - self.z_window_size + 1
        t = (tz + zs) // zs - 1
        z = tz - t * zs
        selection = (int(t), int(ch_idx), slice(z, z + self.z_window_size))
        data = img[selection][np.newaxis]
        return torch.from_numpy(data), (img.name, t, z)

    def __len__(self) -> int:
        return self._max_window

    def __getitem__(self, index: int) -> Sample:
        img, tz = self._find_window(index)
        source, sample_index = self._read_img_window(img, self.source_ch_idx, tz)
        sample = {"source": source, "index": sample_index}
        if self.target_ch_idx is not None:
            sample["target"], _ = self._read_img_window(img, self.target_ch_idx, tz)
        if self.transform:
            sample = self.transform(sample)
        if isinstance(sample, list):
            return sample[0]
        return sample

    def __del__(self):
        self.positions[0].zgroup.store.close()


class HCSDataModule(LightningDataModule):
    """Lightning data module for a preprocessed HCS NGFF Store.

    :param str data_path: path to the data store
    :param str source_channel: name of the source channel, e.g. 'Phase'
    :param str target_channel: name of the target channel, e.g. 'Nuclei'
    :param int z_window_size: Z window size of the 2.5D U-Net, 1 for 2D
    :param float split_ratio: split ratio of the training subset in the fit stage,
        e.g. 0.8 means a 80/20 split between training/validation
    :param int batch_size: batch size, defaults to 16
    :param int num_workers: number of data-loading workers, defaults to 8
    :param Literal["2.5D", "2D", "3D"] architecture: U-Net architecture,
        defaults to "2.5D"
    :param tuple[int, int] yx_patch_size: patch size in (Y, X),
        defaults to (256, 256)
    :param bool augment: whether to apply augmentation in training,
        defaults to True
    :param bool caching: whether to decompress all the images and cache the result,
        defaults to False
    """

    def __init__(
        self,
        data_path: str,
        source_channel: str,
        target_channel: str,
        z_window_size: int,
        split_ratio: float,
        batch_size: int = 16,
        num_workers: int = 8,
        architecture: Literal["2.5D", "2D", "3D"] = "2.5D",
        yx_patch_size: tuple[int, int] = (256, 256),
        augment: bool = True,
        caching: bool = False,
        normalize_source: bool = False,
    ):
        super().__init__()
        self.data_path = data_path
        self.source_channel = source_channel
        self.target_channel = target_channel
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.target_2d = True if architecture == "2.5D" else False
        self.z_window_size = z_window_size
        self.split_ratio = split_ratio
        self.yx_patch_size = yx_patch_size
        self.augment = augment
        self.caching = caching
        self.normalize_source = normalize_source
        self.tmp_zarr = None

    def prepare_data(self):
        if not self.caching:
            return
        # setup logger
        logger = logging.getLogger("viscy_data")
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
        os.mkdir(self.trainer.logger.log_dir)
        file_handler = logging.FileHandler(
            os.path.join(self.trainer.logger.log_dir, "data.log")
        )
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        # cache in temporary directory
        self.tmp_zarr = os.path.join(
            tempfile.gettempdir(), os.path.basename(self.data_path)
        )
        logger.info(f"Caching dataset at {self.tmp_zarr}.")
        tmp_store = zarr.NestedDirectoryStore(self.tmp_zarr)
        with open_ome_zarr(self.data_path, mode="r") as lazy_plate:
            _, skipped, _ = zarr.copy(
                lazy_plate.zgroup,
                zarr.open(tmp_store, mode="a"),
                name="/",
                log=logger.debug,
                if_exists="skip_initialized",
                compressor=None,
            )
        if skipped > 0:
            logger.warning(
                f"Skipped {skipped} items when caching. Check debug log for details."
            )

    def setup(self, stage: Literal["fit", "validate", "test", "predict"]):
        channels = {"source": self.source_channel}
        dataset_settings = dict(channels=channels, z_window_size=self.z_window_size)
        if stage in ("fit", "validate"):
            dataset_settings["channels"]["target"] = self.target_channel
            data_path = self.tmp_zarr if self.tmp_zarr else self.data_path
            plate = open_ome_zarr(data_path, mode="r")
            # disable metadata tracking in MONAI for performance
            set_track_meta(False)
            # define training stage transforms
            norm_keys = ["target"]
            if self.normalize_source:
                norm_keys.append("source")
            normalize_transform = [
                NormalizeSampled(norm_keys, plate.zattrs["normalization"], channels)
            ]
            fit_transform = self._fit_transform()
            train_transform = Compose(
                normalize_transform + self._train_transform() + fit_transform
            )
            val_transform = Compose(normalize_transform + fit_transform)
            # shuffle positions, randomness is handled globally
            positions = [pos for _, pos in plate.positions()]
            shuffled_indices = torch.randperm(len(positions))
            positions = list(positions[i] for i in shuffled_indices)
            num_train_fovs = int(len(positions) * self.split_ratio)
            # train/val split
            self.train_dataset = SlidingWindowDataset(
                positions[:num_train_fovs],
                transform=train_transform,
                **dataset_settings,
            )
            self.val_dataset = SlidingWindowDataset(
                positions[num_train_fovs:], transform=val_transform, **dataset_settings
            )
        elif stage == "predict":
            # track metadata for inverting transform
            set_track_meta(True)
            if self.caching:
                logging.warning("Ignoring caching config in 'predict' stage.")
            plate = open_ome_zarr(self.data_path, mode="r")
            predict_transform = (
                NormalizeSampled(norm_keys, plate.zattrs["normalization"], channels)
                if self.normalize_source
                else None
            )
            self.predict_dataset = SlidingWindowDataset(
                [p for _, p in plate.positions()],
                transform=predict_transform,
                **dataset_settings,
            )
        # test stage
        else:
            raise NotImplementedError(f"{stage} stage")

    def on_before_batch_transfer(self, batch: Sample, dataloader_idx: int) -> Sample:
        if self.trainer.testing or self.trainer.predicting:
            return batch
        if self.target_2d and not isinstance(batch, torch.Tensor):
            # slice the center during training, skipping example input array
            batch["target"] = batch["target"][:, :, self.z_window_size // 2][:, :, None]
        return batch

    def train_dataloader(self):
        return DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=True,
            persistent_workers=True,
        )

    def val_dataloader(self):
        return DataLoader(
            self.val_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=False,
            persistent_workers=True,
        )

    def predict_dataloader(self):
        return DataLoader(
            self.predict_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=False,
        )

    def _fit_transform(self):
        return [
            CenterSpatialCropd(
                keys=["source", "target"],
                roi_size=(
                    -1,
                    self.yx_patch_size[0],
                    self.yx_patch_size[1],
                ),
            )
        ]

    def _train_transform(self) -> list[Callable]:
        transforms = [
            RandWeightedCropd(
                keys=["source", "target"],
                w_key="target",
                spatial_size=(-1, self.yx_patch_size[0] * 2, self.yx_patch_size[1] * 2),
                num_samples=1,
            )
        ]
        if self.augment:
            transforms.extend(
                [
                    RandAffined(
                        keys=["source", "target"],
                        prob=0.5,
                        rotate_range=(np.pi, 0, 0),
                        shear_range=(0, (0.05), (0.05)),
                        scale_range=(0, 0.3, 0.3),
                    ),
                    RandAdjustContrastd(keys=["source"], prob=0.3, gamma=(0.75, 1.5)),
                    RandGaussianSmoothd(
                        keys=["source"],
                        prob=0.3,
                        sigma_x=(0.05, 0.25),
                        sigma_y=(0.05, 0.25),
                        sigma_z=((0.05, 0.25)),
                    ),
                ]
            )
        return transforms
