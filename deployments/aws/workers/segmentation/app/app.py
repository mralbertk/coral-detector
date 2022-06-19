import boto3, cv2, os, urllib.parse
import numpy as np
from datetime import date
from detectron2 import model_zoo
from detectron2.config import get_cfg
from detectron2.engine import DefaultPredictor
from detectron2.utils.visualizer import Visualizer, ColorMode
from detectron2.data import DatasetCatalog, MetadataCatalog


def handler(event, context):
    """TODO: Docstring"""

    # Internal storage configuration
    image_path = "/tmp/image.jpg"
    output_path = "/tmp/output.jpg"
    mask_path = "/tmp/output-mask.jpg"
    m_path = "/tmp/model.pth"

    # DB connection configuration TODO: Parameterize
    db_name = "criobe_corals"
    db_cluster_arn = "arn:aws:rds:eu-west-1:950138825908:cluster:dsti-criobe-db"
    db_credentials_secret_store_arn = "arn:aws:secretsmanager:eu-west-1:950138825908:secret:rds-db-credentials/cluster-AIT5MBWGBYEYUB6C6HBFTP5GR4/dsti_criobe_app-L17eZ0"

    # Connect to AWS services & configure
    s3_client = boto3.client("s3")
    rds_client = boto3.client("rds-data")

    # Output image name matches input name
    s3_image_output = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['object']['key'], encoding='utf-8'
    )

    s3_image_output_split = s3_image_output.split(".")
    s3_mask_output = f"{s3_image_output_split[0]}-mask.{s3_image_output_split[-1]}"

    # Some values for the DB entry based on input file name
    db_inputs = s3_image_output_split[0].split("-")
    db_year = db_inputs[0]
    db_island = db_inputs[1]
    db_location = db_inputs[2]

    # TODO: Parameterize output bucket
    s3_bucket_output = "criobe-images-segmented"
    s3_bucket_masks = "criobe-images-masks"

    # TODO: Parameterize model path
    s3_model_bucket = "criobe-models-segmentation"
    s3_model_name = "detectron2-classifier.pth"

    # Get input image object & bucket from event
    s3_image_input = s3_image_output

    s3_bucket_input = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['bucket']['name'], encoding='utf-8'
    )

    # Download image to container
    with open(image_path, 'wb') as f:
        s3_client.download_fileobj(s3_bucket_input, s3_image_input, f)

    # Download model to container
    with open(m_path, 'wb') as f:
        s3_client.download_fileobj(s3_model_bucket, s3_model_name, f)

    # Detect corals
    detector = custom_config(model_path=m_path)
    corals = segmentation(detector, image_path, output_path)

    # Save new image & mask to S3
    s3_client.upload_file(output_path, s3_bucket_output, s3_image_output)
    s3_client.upload_file(mask_path, s3_bucket_masks, s3_mask_output)

    # Write coral coverage to RDS
    db_write(rds_client,
             db_island,
             db_location,
             db_year,
             corals,
             db_name,
             db_cluster_arn,
             db_credentials_secret_store_arn)

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application-json"
        },
        "body": {
            "image-bucket": s3_bucket_output,
            "image-object": s3_image_output,
            "mask-bucket": s3_bucket_masks,
            "mask-object": s3_mask_output,
            "coverage": corals,
        }
    }


#   /------------------------------------------------/
#  /            Custom Configuration                /
# /------------------------------------------------/

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


#   /------------------------------------------------/
#  /                    Inference                   /
# /------------------------------------------------/


def segmentation(classifier, infile, outfile):
    """Performs coral detection on an image file.

    The segmented image and the binary mask are uploaded to AWS S3.

    Args:
        classifier: A Detectron2 model trained for coral detection.
        infile: A path to a source image on which to perform segmentation.
        outfile: A destination path to write the segmented image to.

    Returns:
        n of non-zero pixels / n of total pixels
    """
    outfile_split = outfile.split(".")
    mask_outfile = f"{''.join(outfile_split[:-1])}-mask.{outfile_split[-1]}"
    img = cv2.imread(infile)
    output = classifier(img)

    # Build binary mask
    masks = 1 * output["instances"].get("pred_masks").numpy()
    bin_mask = np.zeros(img.shape[:-1])
    for mask in masks:
        mask_bin = np.where(mask == False, 0, 255)
        bin_mask += mask_bin

    # Register a dataset and metadata
    DatasetCatalog.register("my_corals", lambda: [{}])  # Oh God ...
    MetadataCatalog.get("my_corals").thing_classes = ["is_coral"]
    MetadataCatalog.get("my_corals").thing_colors = [(0, 255, 0)]

    # Get Segmented Image
    v = Visualizer(img[:, :, ::-1],
                   metadata=MetadataCatalog.get("my_corals"),
                   instance_mode=ColorMode.SEGMENTATION,
                   scale=1.0)
    out = v.draw_instance_predictions(output["instances"])

    # Write results
    cv2.imwrite(outfile, out.get_image()[:, :, ::-1])
    cv2.imwrite(mask_outfile, bin_mask)

    # Return coral coverage
    return round((np.count_nonzero(bin_mask) / bin_mask.size) * 100, 2)


#   /------------------------------------------------/
#  /              Database Output                   /
# /------------------------------------------------/


def db_write(client, island, location, year, coverage,
             db, cluster, credentials):
    """Writes coral coverage into a relational database

    Args:
        client: A boto3 rds-data client object
        island: A string
        location: An integer
        year: An integer
        coverage: A float
        db: A database name as string
        cluster: An AWS Aurora cluster ARN as string
        credentials: An AWS secret store ARN as string

    Returns:
        None
    """
    insert_set = [
        {"name": "island", "value": {"stringValue": island}},
        {"name": "location", "value": {"longValue": int(location)}},
        {"name": "year", "value": {"longValue": int(year)}},
        {"name": "coverage", "value": {"doubleValue": coverage}},
        {"name": "last_update", "value": {"stringValue": str(date.today())}}
    ]

    insert_statement = """
        INSERT INTO coral_coverage 
        (island, location, year, coverage, last_update)
        VALUES(:island, :location, :year, :coverage, :last_update)
        ON DUPLICATE KEY UPDATE 
        coverage = VALUES(coverage),
        last_update = VALUES(last_update); 
    """

    client.execute_statement(
        secretArn=credentials,
        database=db,
        resourceArn=cluster,
        sql=insert_statement,
        parameters=insert_set
    )
