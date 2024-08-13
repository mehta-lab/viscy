# %%
from pathlib import Path

import pandas as pd
import seaborn as sns
from plotly.express import scatter
from sklearn.preprocessing import StandardScaler
from umap import UMAP

from viscy.light.embedding_writer import read_embedding_dataset

# %%
dataset = read_embedding_dataset(
    "/hpc/projects/intracellular_dashboard/viral-sensor/infection_classification/models/contrastive_tune_augmentations/predict/2024_02_04-tokenized-drop_path_0_0.zarr"
)
dataset

# %%
# load all unprojected features:
features = dataset["features"]
# or select a well:
# features - features[features["fov_name"].str.contains("B/4")]
features

# %%
scaled_features = StandardScaler().fit_transform(features.values)

umap = UMAP()

embedding = umap.fit_transform(scaled_features)
embedding.shape

# %%
sns.scatterplot(x=embedding[:, 0], y=embedding[:, 1], hue=features["t"], s=7, alpha=0.8)


# %%
def load_annotation(da, path, name, categories: dict | None = None):
    annotation = pd.read_csv(path)
    annotation["fov_name"] = "/" + annotation["fov ID"]
    annotation = annotation.set_index(["fov_name", "id"])
    mi = pd.MultiIndex.from_arrays(
        [da["fov_name"].values, da["id"].values], names=["fov_name", "id"]
    )
    selected = annotation.loc[mi][name]
    if categories:
        selected = selected.astype("category").cat.rename_categories(categories)
    return selected


# %%
ann_root = Path(
    "/hpc/projects/intracellular_dashboard/viral-sensor/2024_02_04_A549_DENV_ZIKV_timelapse/7.1-seg_track"
)

infection = load_annotation(
    features,
    ann_root / "tracking_v1_infection.csv",
    "infection class",
    {0.0: "background", 1.0: "uninfected", 2.0: "infected"},
)
division = load_annotation(
    features,
    ann_root / "cell_division_state.csv",
    "division",
    {0: "non-dividing", 2: "dividing"},
)


# %%
sns.scatterplot(x=embedding[:, 0], y=embedding[:, 1], hue=division, s=7, alpha=0.8)

# %%
sns.scatterplot(x=embedding[:, 0], y=embedding[:, 1], hue=infection, s=7, alpha=0.8)

# %%
ax = sns.histplot(x=embedding[:, 0], y=embedding[:, 1], hue=infection, bins=64)
sns.move_legend(ax, loc="lower left")

# %%
ax = sns.displot(
    x=embedding[:, 0],
    y=embedding[:, 1],
    kind="hist",
    col=infection,
    bins=64,
    cmap="inferno",
)

# %%
# interactive scatter plot to associate clusters with specific cells
scatter(
    x=embedding[:, 0],
    y=embedding[:, 1],
    color=(infection.astype(str) + " " + division.astype(str)),
    hover_name=features["fov_name"] + "/" + features["id"].astype(str),
)

# %%
# cluster features in heatmap directly
inf_codes = pd.Series(infection.values.codes, name="infection")
lut = dict(zip(inf_codes.unique(), "brw"))
row_colors = inf_codes.map(lut)

g = sns.clustermap(
    scaled_features, row_colors=row_colors.to_numpy(), col_cluster=False, cbar_pos=None
)
g.yaxis.set_ticks([])
# %%
