import boto3
import cv2
import rawpy
import numpy as np
import urllib.parse
from PIL import Image


def handler(event, context):
    """
    TODO: Add docstring
    """

    # Internal storage configuration
    image_path = "/tmp/image"
    output_path = "/tmp/output.jpg"

    # Connect to S3 & configure output
    s3_client = boto3.client("s3")

    # Output image name matches input name
    s3_image_output = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['object']['key'], encoding='utf-8'
    )

    # TODO: Parameterize output bucket name
    s3_bucket_output = "criobe-images-treated"

    # Get input image object & bucket from event
    s3_image_input = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['object']['key'], encoding='utf-8'
    )

    s3_bucket_input = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['bucket']['name'], encoding='utf-8'
    )

    # Download image to container
    with open(image_path, 'wb') as f:
        s3_client.download_fileobj(s3_bucket_input, s3_image_input, f)

    # If the S3 image is in raw format, convert to jpg
    if s3_image_input.split(".")[-1].lower() == "nef":
        with rawpy.imread(image_path) as raw:
            rgb_image = raw.postprocess()
        converted_image = Image.fromarray(rgb_image)
        converted_image.save(".".join([image_path, "jpg"]))

        # Update output file to reflect format change
        s3_image_output = ".".join([s3_image_output.split(".")[0], "jpg"])

    # Perform Histogram Equalization
    image = np.array(Image.open(".".join([image_path, "jpg"])))
    image = cv2.cvtColor(image, cv2.cv2.COLOR_RGB2BGR)

    for i in range(3):
        image[:, :, i] = cv2.equalizeHist(image[:, :, i])

    cv2.imwrite(output_path, image)

    # Save new image to S3
    s3_client.upload_file(output_path, s3_bucket_output, s3_image_output)

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application-json"
        },
        "body": {
            "image-bucket": s3_bucket_output,
            "image-object": s3_image_output
        }
    }
