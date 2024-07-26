import timm
import torch.nn as nn
import torch.nn.functional as F

# from viscy.unet.networks.resnet import resnetStem
# Currently identical to resnetStem, but could be different in the future.
from viscy.unet.networks.unext2 import UNeXt2Stem
from viscy.unet.networks.unext2 import StemDepthtoChannels


class ContrastiveEncoder(nn.Module):
    def __init__(
        self,
        backbone: str = "convnext_tiny",
        in_channels: int = 2,
        in_stack_depth: int = 15,
        stem_kernel_size: tuple[int, int, int] = (5, 3, 3),
        embedding_len: int = 256,
        stem_stride: int = 2,
        predict: bool = False,
    ):
        super().__init__()

        self.predict = predict
        self.backbone = backbone

        """
        ContrastiveEncoder network that uses ConvNext and ResNet backbons from timm.

        Parameters:
        - backbone (str): Backbone architecture for the encoder. Default is "convnext_tiny".
        - in_channels (int): Number of input channels. Default is 2.
        - in_stack_depth (int): Number of input slices in z-stack. Default is 15.
        - stem_kernel_size (tuple[int, int, int]): 3D kernel size for the stem. Input stack depth must be divisible by the kernel depth. Default is (5, 3, 3).
        - embedding_len (int): Length of the embedding. Default is 1000.
        """

        # encoder from timm
        encoder = timm.create_model(
            backbone,
            pretrained=True,
            features_only=False,
            drop_path_rate=0.2,
            num_classes=3 * embedding_len,
        )

        # Do encoder surgery and setup stem and projection head.

        if "convnext" in backbone:
            # replace the stem designed for RGB images with a stem designed to handle 3D multi-channel input.
            in_channels_encoder = encoder.stem[0].out_channels
            # in_channels_encoder can be 96 or 64, and in_channels can be 1,2,or 3.

            # Remove the convolution layer of stem, but keep the layernorm.
            encoder.stem[0] = nn.Identity()

            # Save projection head separately and erase the projection head contained within the encoder.
            projection = nn.Sequential(
                nn.Linear(encoder.head.fc.in_features, 3 * embedding_len),
                nn.ReLU(inplace=True),
                nn.Linear(3 * embedding_len, embedding_len),
            )
            encoder.head.fc = nn.Identity()

        # TO-DO: need to debug further
        elif "resnet" in backbone:
            in_channels_encoder = encoder.conv1.out_channels
            encoder.conv1 = nn.Identity()

            projection = nn.Sequential(
                nn.Linear(encoder.fc.in_features, 3 * embedding_len),
                nn.ReLU(inplace=True),
                nn.Linear(3 * embedding_len, embedding_len),
            )
            encoder.fc = nn.Identity()

        # Create a new stem that can handle 3D multi-channel input.
        self.stem = StemDepthtoChannels(
            in_channels, in_stack_depth, in_channels_encoder
        )
        # Append modified encoder.
        self.encoder = encoder
        # Append modified projection head.
        self.projection = projection

    def forward(self, x):
        x = self.stem(x)
        embedding = self.encoder(x)
        projections = self.projection(embedding)
        return (
            embedding,
            projections,
        )  # Compute the loss on projections, analyze the embeddings.
