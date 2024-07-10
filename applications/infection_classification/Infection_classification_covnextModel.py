# %%
# import sys
# sys.path.append("/hpc/mydata/soorya.pradeep/viscy_infection_phenotyping/Viscy/")
import torch
import lightning.pytorch as pl
import torch.nn as nn

from pytorch_lightning.loggers import TensorBoardLogger
from pytorch_lightning.callbacks import ModelCheckpoint

from viscy.transforms import RandWeightedCropd
from viscy.transforms import NormalizeSampled
from viscy.data.hcs import HCSDataModule
from applications.infection_classification.classify_infection_covnext import (
    SemanticSegUNet22D,
)
from viscy.preprocessing import calculate_pixel_ratio

# %% Create a dataloader and visualize the batches.

# Set the path to the dataset
dataset_path = "/hpc/projects/intracellular_dashboard/viral-sensor/infection_classification/datasets/Exp_2023_11_08_Opencell_infection/OC43_infection_timelapse_all_curated_train.zarr"

# %% craete data module

# Create an instance of HCSDataModule
data_module = HCSDataModule(
    dataset_path,
    source_channel=["Phase", "HSP90", "phase_nucl_iqr", "hsp90_skew"],
    target_channel=["Inf_mask"],
    yx_patch_size=[256, 256],
    split_ratio=0.8,
    z_window_size=5,
    architecture="2.2D",
    num_workers=3,
    batch_size=16,
    normalizations=[
        NormalizeSampled(
            keys=["Phase", "HSP90", "phase_nucl_iqr", "hsp90_skew"],
            level="fov_statistics",
            subtrahend="median",
            divisor="iqr",
        )
    ],
    augmentations=[
        RandWeightedCropd(
            num_samples=4,
            spatial_size=[-1, 256, 256],
            keys=["Phase", "HSP90", "phase_nucl_iqr", "hsp90_skew"],
            w_key="Inf_mask",
        )
    ],
)
pixel_ratio = calculate_pixel_ratio(dataset_path, target_channel="Inf_mask")

# Prepare the data
data_module.prepare_data()

# Setup the data
data_module.setup(stage="fit")

# Create a dataloader
train_dm = data_module.train_dataloader()

val_dm = data_module.val_dataloader()


# %% Define the logger
logger = TensorBoardLogger(
    "/hpc/projects/intracellular_dashboard/viral-sensor/infection_classification/models/sensorInf_phenotyping/mantis_phase_hsp90/",
    name="logs",
)

# Pass the logger to the Trainer
trainer = pl.Trainer(
    logger=logger,
    max_epochs=200,
    default_root_dir="/hpc/projects/intracellular_dashboard/viral-sensor/infection_classification/models/sensorInf_phenotyping/mantis_phase_hsp90/logs/",
    log_every_n_steps=1,
    devices=1,  # Set the number of GPUs to use. This avoids run-time exception from distributed training when the node has multiple GPUs
)

# Define the checkpoint callback
checkpoint_callback = ModelCheckpoint(
    dirpath="/hpc/projects/intracellular_dashboard/viral-sensor/infection_classification/models/sensorInf_phenotyping/mantis_phase_hsp90/logs/",
    filename="checkpoint_{epoch:02d}",
    save_top_k=-1,
    verbose=True,
    monitor="loss/validate",
    mode="min",
)

# Add the checkpoint callback to the trainer``
trainer.callbacks.append(checkpoint_callback)

# Fit the model
model = SemanticSegUNet22D(
    in_channels=4,
    out_channels=3,
    loss_function=nn.CrossEntropyLoss(weight=torch.tensor(pixel_ratio)),
)

print(model)

# %% Run training.

trainer.fit(model, data_module)

# %%
