# %%
from torchview import draw_graph

from viscy.light.engine import FcmaeUNet, VSUNet

# %% 2D UNet
model = VSUNet(
    architecture="2D",
    model_config={"in_channels": 1, "out_channels": 2},
)
# %%
model_graph = draw_graph(
    model,
    model.example_input_array,
    graph_name="2D UNet",
    roll=True,
    depth=4,
    # graph_dir="LR",
    # save_graph=True,
)

graph2d = model_graph.visual_graph
graph2d

# %% 2.5D UNet
model = VSUNet(
    architecture="2.5D",
    model_config={
        "in_channels": 1,
        "out_channels": 3,
        "in_stack_depth": 9,
    },
)

model_graph = draw_graph(
    model,
    model.example_input_array,
    graph_name="2.5D UNet",
    roll=True,
    depth=2,
)

graph25d = model_graph.visual_graph
graph25d

# %%
# 2.1D UNet without upsampling in Z.
model = VSUNet(
    architecture="2.1D",
    model_config={
        "in_channels": 2,
        "out_channels": 1,
        "in_stack_depth": 9,
        "backbone": "convnextv2_tiny",
        "stem_kernel_size": (3, 1, 1),
        "decoder_mode": "pixelshuffle",
    },
)

model_graph = draw_graph(
    model,
    model.example_input_array,
    graph_name="2.1D UNet",
    roll=True,
    depth=3,
)

graph21d = model_graph.visual_graph
graph21d
# %%
# 2.1D UNet with upsampling in Z.
model = VSUNet(
    architecture="2.2D",
    model_config={
        "in_channels": 1,
        "out_channels": 2,
        "in_stack_depth": 9,
        "backbone": "convnextv2_tiny",
        "decoder_mode": "pixelshuffle",
        "stem_kernel_size": (3, 4, 4),
    },
)

model_graph = draw_graph(
    model,
    model.example_input_array,
    graph_name="2.2D UNet",
    roll=True,
    depth=3,
)

graph22d = model_graph.visual_graph
graph22d
# %% If you want to save the graphs as SVG files:
# model_graph.visual_graph.render(format="svg")

# %%
model = FcmaeUNet(
    model_config=dict(
        in_channels=1,
        out_channels=1,
        encoder_blocks=[3, 3, 9, 3],
        dims=[96, 192, 384, 768],
        decoder_conv_blocks=1,
        stem_kernel_size=(1, 2, 2),
        in_stack_depth=1,
    ),
    fit_mask_ratio=0.5,
    schedule="WarmupCosine",
    lr=2e-4,
    log_batches_per_epoch=2,
    log_samples_per_batch=2,
)

model_graph = draw_graph(
    model,
    (model.example_input_array),
    graph_name="VSCyto2D",
    roll=True,
    depth=3,
)

fcmae = model_graph.visual_graph
fcmae

# %%

model_graph.visual_graph.render(
    format="svg",
)

# %%
