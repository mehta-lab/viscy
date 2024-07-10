from iohub.ngff import open_ome_zarr

from viscy.preprocessing.pixel_ratio import sematic_class_weights


def test_sematic_class_weights(small_hcs_dataset):
    weights = sematic_class_weights(small_hcs_dataset, "GFP")
    assert weights.shape == (3,)
    assert weights[0] == 1.0
    # infinity
    assert weights[1] > 1.0
    assert weights[2] > 1.0