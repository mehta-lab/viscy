import os
import random
import torch
import numpy as np
from torch.utils.data import Dataset, DataLoader
from viscy.transforms import RandAdjustContrastd, RandAffined, RandGaussianNoised, RandGaussianSmoothd, RandScaleIntensityd
from monai.transforms import Compose
from iohub import open_ome_zarr

class OMEZarrDataset(Dataset):
    def __init__(self, base_path, channels, x, y, z, transform=None, z_range=None):
        self.base_path = base_path
        self.channels = channels
        self.x = x
        self.y = y
        self.z = z
        self.z_range = z_range
        self.transform = transform
        self.ds = self.open_zarr_store(self.base_path)
        self.positions = list(self.ds.positions())
        print(f"Initialized dataset with {len(self.positions)} positions.")

    def open_zarr_store(self, path, layout="hcs", mode="r"):
        print(f"Opening Zarr store at {path} with layout '{layout}' and mode '{mode}'")
        return open_ome_zarr(path, layout=layout, mode=mode)

    def __len__(self):
        return len(self.positions)

    def __getitem__(self, idx):
        anchor_position_path = self.positions[idx][0]
        anchor_data = self.load_data(anchor_position_path)

        positive_data = self.transform({'image': anchor_data})['image'] if self.transform else anchor_data

        negative_idx = idx
        while negative_idx == idx:
            negative_idx = random.randint(0, self.__len__() - 1)
        negative_position_path = self.positions[negative_idx][0]
        negative_data = self.load_data(negative_position_path)

        negative_data = self.transform({'image': anchor_data})['image'] if self.transform else negative_data

        print("shapes of tensors")
        print(torch.tensor(anchor_data).shape)
        print(torch.tensor(positive_data).shape)
        print(torch.tensor(negative_data).shape)
        return torch.tensor(anchor_data), torch.tensor(positive_data), torch.tensor(negative_data)

    def load_data(self, position_path):
        position = self.ds[position_path]
        print(f"Loading data from position: {position_path}")
        zarr_array = position['0'][:]
        print('Shape before:', zarr_array.shape)
        data = self.restructure_data(zarr_array)
        if self.z_range:
            data = data[:, self.z_range[0]:self.z_range[1], :, :]
        print("Shape after:", data.shape)
        return data

    def restructure_data(self, data):
        # randomly sample a timestep and index into that
        timesteps = data.shape[0]
        random_timestep = np.random.randint(timesteps)
        reshaped_data = data[random_timestep]  
        return reshaped_data

def get_transforms():
    transforms = Compose([
        RandAdjustContrastd(keys=['image'], prob=0.5, gamma=(0.5, 2.0)),
        RandAffined(keys=['image'], prob=0.5, rotate_range=(0.2, 0.2), shear_range=(0.2, 0.2), scale_range=(0.2, 0.2)),
        RandGaussianNoised(keys=['image'], prob=0.5, mean=0.0, std=0.1),
        RandGaussianSmoothd(keys=['image'], prob=0.5, sigma_x=(0.5, 1.0), sigma_y=(0.5, 1.0), sigma_z=(0.5, 1.0)),
        RandScaleIntensityd(keys=['image'], factors=(0.5, 2.0), prob=0.5),
    ])
    return transforms

base_path = "/hpc/projects/intracellular_dashboard/viral-sensor/2024_02_04_A549_DENV_ZIKV_timelapse/6-patches/small_patch.zarr"
channels = 2  
x = 200       
y = 200       
z = 15        
z_range = (0, 10)  
batch_size = 4

dataset = OMEZarrDataset(base_path, channels, x, y, z, transform=get_transforms(), z_range=z_range)
dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

# print the shape of batches from the DataLoader
for batch in dataloader:
    anchor_batch, positive_batch, negative_batch = batch
    print("Batch shapes:")
    print("Anchor batch shape:", anchor_batch.shape)
    print("Positive batch shape:", positive_batch.shape)
    print("Negative batch shape:", negative_batch.shape)
    break
