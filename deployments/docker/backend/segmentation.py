import os
import numpy as np
from detectron2 import model_zoo
from detectron2.config import get_cfg
from detectron2.engine import DefaultPredictor
from detectron2.utils.visualizer import Visualizer, ColorMode
from detectron2.data import DatasetCatalog, MetadataCatalog


def segmentation(m_path, img):
    """Performs coral detection on an image file.

    Args:
        m_path: A path to the segmentation model
        infile: A path to a source image on which to perform segmentation.

    Returns:
        n of non-zero pixels / n of total pixels
    """
    classifier = custom_config(model_path=m_path)
    output = classifier(img)

    # Build binary mask
    masks = 1 * output["instances"].get("pred_masks").numpy()
    bin_mask = np.zeros(img.shape[:-1])
    for mask in masks:
        mask_bin = np.where(mask == False, 0, 255)
        bin_mask += mask_bin

    # Compute coral coverage
    coral_coverage = round(np.count_nonzero(bin_mask) / bin_mask.size, 8)

    # Register a dataset and metadata
    try:
        DatasetCatalog.register("my_corals", lambda: [{}])  # Oh God ...
        MetadataCatalog.get("my_corals").thing_classes = ["is_coral"]
        MetadataCatalog.get("my_corals").thing_colors = [(0, 255, 0)]
    except AssertionError:
        print("Using existing catalog.")

    # Get Segmented Image
    v = Visualizer(img[:, :, ::-1],
                   metadata=MetadataCatalog.get("my_corals"),
                   instance_mode=ColorMode.SEGMENTATION,
                   scale=1.0)
    out = v.draw_instance_predictions(output["instances"])
    img = out.get_image()[:, :, ::-1]
    img = img[:, :, [2, 1, 0]]

    # Return coral coverage
    return img, bin_mask, coral_coverage


def custom_config(model_path=None):
    """Load a Detectron2 model.

    Args:
        model_path: A relative path to model.pth

    Returns:
        predictor: A Detectron2 callable ready for inference
    """

    cfg = get_cfg()
    cfg.MODEL.DEVICE = 'cpu'  # comment this line if you can use a GPU

    # get configuration from model_zoo
    config_file = "COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"
    cfg.merge_from_file(model_zoo.get_config_file(config_file))

    # initialize weights
    if not model_path:
        cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url(config_file)
    else:
        assert os.path.isfile(model_path), '.pth file not found'
        cfg.MODEL.WEIGHTS = model_path

    cfg.MODEL.ROI_HEADS.NUM_CLASSES = 1  # only has one class (is_coral).
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.7  # set a custom testing threshold

    predictor = DefaultPredictor(cfg)

    return predictor


