import boto3
import cv2
import imutils
import os
import urllib.parse
import numpy as np
from detectron2 import model_zoo
from detectron2.config import get_cfg
from detectron2.engine import DefaultPredictor
from PIL import Image


# This class should be in its own library, but we need to understand
# Python custom library management better before implementing properly
class ParamGetter:
    """Recursively retrieves parameters from Amazon SSM.

    Args:
        param_path: A string, prefix of all parameters to look up
    """

    def __init__(self, param_path):
        self.p_path = param_path
        self.params = self.get_params()

    def get_params(self):
        ssm = boto3.client("ssm", region_name="eu-west-1")
        params = {}
        ssm_paginator = ssm.get_paginator("get_parameters_by_path")
        response_iterator = ssm_paginator.paginate(
            Path=self.p_path,
            Recursive=True)
        for response in response_iterator:
            for param in response["Parameters"]:
                params[param["Name"].split("/")[-1]] = param["Value"]
        return params


def handler(event, context):
    """TODO: Add docstring"""

    # Internal storage configuration
    image_path = "/tmp/image.jpg"
    output_path = "/tmp/output.jpg"
    m_path = "/tmp/model.pth"

    # Connect to S3 & configure
    s3_client = boto3.client("s3")

    # Output image name matches input name
    s3_image_output = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['object']['key'], encoding='utf-8'
    )

    # S3 resource configuration
    params = ParamGetter('/coral-detector/').params
    s3_bucket_output = params["s3_images_reframed"]
    s3_model_bucket = params["s3_model_reframing"]
    s3_model_name = params["s3_reframing_model"]

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

    # Reframe
    reframe(m_path, image_path)

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


def reframe(model_path, file, new_size=400):
    """
    Detects square frame in images. Rotates the frame so that
    it sits straight in the frame. Crops the image to the frame
    border.

    :param model_path: Path to trained model performing the detection
    :param file: Path to the image to modify
    :param new_size: Size of the output image in pixels
    """
    # Load predictor from model
    predictor = custom_config(model_path=model_path)

    # Read image
    image = np.array(Image.open(file))

    # Invert to BGR for CV2
    img = image[:, :, [2, 1, 0]]

    # Current image dimensions
    rows, cols = img.shape[:2]

    # Prediction
    output = predictor(img)

    # Get mask
    mask_array = 1 * output["instances"].get('pred_masks').to('cpu').numpy()
    mask_array = np.moveaxis(mask_array, 0, -1)
    mask_array = np.repeat(mask_array, 3, axis=2)
    output = np.where(mask_array == False, 0,
                      (np.where(mask_array == True, 255, img)))

    mask3d = output
    mask = mask3d[:, :, 1]

    # Find contour of the mask
    contours = find_contour(mask)

    # Fist step : First corners estimations
    screen_contour = minimum_area_enclosing(contours)

    # Second step: Fit 4 lines on each edges
    lines_pts = fit_lines_on_edges(contours, screen_contour, rows, cols)

    # Third step: Lines intersection to get corners
    new_contour = get_lines_intersections(lines_pts, ncols=cols, nrows=rows)

    # Last step: Reframe
    warped = warping(img, pts=np.float32(new_contour[:, 0]), new_size=new_size)

    # Save new image to internal file system
    name = '/tmp/output.jpg'
    cv2.imwrite(name, warped)

    return 1


#   /------------------------------------------------/
#  /            Find contours of the frame          /
# /------------------------------------------------/

def find_contour(mask):
    """
    TODO: Add Docstring
    """

    # find the contours of the mask
    contour = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    contour = imutils.grab_contours(contour)

    # keep only the biggest one
    contour = sorted(contour, key=cv2.contourArea, reverse=True)[:1]
    contour = contour[0]

    assert contour.shape[1:] == (1, 2), "contour.shape[1:] should be (1,2)"
    return contour


def minimum_area_enclosing(contour):
    """
    Find the minimum-area rotated rectangle that encloses the given contour
    """
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    box = np.int0(box)
    screen_cnt = np.array([[i] for i in box.tolist()])
    return screen_cnt


def fit_lines_on_edges(contour, screen_contour, rows, cols, threshold=100, epsilon=100):
    """
    Input:
    - contour: the full contour
    - screen_contour: 4 estimated corners of the contour, obtained with methods 1 or 2
    Steps:
    - For each side, delimited by 2 consecutive corners of screen_contour (c1 and c2)
    - Find all the points of contour that are located between c1 and c2 (+- margin)
    - Fit a line, using cv2.fitLine, on these points
    Output:
    - pts: the list of the 4 fitted lines
         Ex: [[[1,2], [3,4]], # line 1 passes through point [1,2] and [3,4]
              [[5,6], [7,8]],
              [[9,10], [11,12]],
              [[13,14], [15,16]]]
    """

    assert screen_contour.shape == (4, 1, 2), 'screen_contour.shape should be (4, 1, 2)'

    X = [i[0][0] for i in contour]
    Y = [i[0][1] for i in contour]

    left_y = []
    right_y = []
    left_x = []
    right_x = []
    cut_contour = []
    c_list = [0, 1, 2, 3, 0]

    for edge in range(4):
        # define 2 extreme points of the edge
        c1 = screen_contour[c_list[edge]][0]
        c2 = screen_contour[c_list[edge + 1]][0]

        # select all the contour points that are located between these 2 points +- margin --> cut_contour
        if abs(c1[0] - c2[0]) < threshold:  # if the 2 pts have almost the same abscissa
            c_mean = (c1[0] + c2[0]) / 2
            x_margin = [max(0, c_mean - epsilon), min(c_mean + epsilon, cols)]
            y_margin = sorted([c1[1], c2[1]])

        elif abs(c1[1] - c2[1]) < threshold:  # if the 2 pts have almost the same ordinate
            c_mean = (c1[1] + c2[1]) / 2
            x_margin = sorted([c1[0], c2[0]])
            y_margin = [max(0, c_mean - epsilon), min(c_mean + epsilon, rows)]

        else:
            x_margin = sorted([c1[0], c2[0]])
            y_margin = sorted([c1[1], c2[1]])

        c = [[[X[ind], Y[ind]]] for ind in range(len(X)) if
             x_margin[0] <= X[ind] <= x_margin[1] and y_margin[0] <= Y[ind] <= y_margin[1]]
        cut_contour.append(np.array(c))

        # fit a line on c
        [vx, vy, x, y] = cv2.fitLine(np.array(c), cv2.DIST_L2, 0, 0.01, 0.01)

        # append the result for this edge to left and right points
        left_x.append(0)
        right_x.append(cols)
        left_y.append(int((-x * vy / vx) + y))
        right_y.append(int(((cols - x) * vy / vx) + y))

    #
    pts = [[[left_x[ind], left_y[ind]], [right_x[ind], right_y[ind]]] for ind in range(4)]
    return pts


#   /------------------------------------------------/
#  /            Custom Configuration                /
# /------------------------------------------------/

def custom_config(model_path=None):
    """
    TODO: Add Docstring
    """

    cfg = get_cfg()
    cfg.MODEL.DEVICE = 'cpu'  # comment this line if you can use a GPU

    # get configuration from model_zoo
    config_file = "COCO-InstanceSegmentation/mask_rcnn_R_101_FPN_3x.yaml"
    cfg.merge_from_file(model_zoo.get_config_file(config_file))

    # initialize weights
    if not model_path:
        cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url(config_file)
    else:
        assert os.path.isfile(model_path), '.pth file not found'
        cfg.MODEL.WEIGHTS = model_path

    cfg.MODEL.ROI_HEADS.NUM_CLASSES = 1  # only has one class (square).
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.7  # set a custom testing threshold

    predictor = DefaultPredictor(cfg)

    return predictor


#   /------------------------------------------------/
#  /                   Intersection                 /
# /------------------------------------------------/

def line(p1, p2):
    """
    Produces coefs a, b, c of line equation by two points provided
    Ex: L1 = line([2,3], [4,0]) --> L1 = (3, 2, 12)
    """
    a = (p1[1] - p2[1])
    b = (p2[0] - p1[0])
    c = (p1[0] * p2[1] - p2[0] * p1[1])
    return a, b, -c


def intersection(L1, L2):
    """
    Finds intersection point (if any) of two lines provided by coefs.
    Ex: L1 = line([0,1], [2,3])
        L2 = line([2,3], [4,0])
        intersec = intersection(L1,L2) --> intersec = [2, 3]
        L1 = line([0,1], [2,3])
        L2 = line([0,2], [2,4])
        intersect = intersection(L1,L2) --> None
    """
    d = L1[0] * L2[1] - L1[1] * L2[0]
    dx = L1[2] * L2[1] - L1[1] * L2[2]
    dy = L1[0] * L2[2] - L1[2] * L2[0]

    if d != 0:
        x = dx / d
        y = dy / d
        return [int(x), int(y)]
    else:
        return None


def get_lines_intersections(pts, ncols=1e158, nrows=1e158):
    """
    Input: A list of 4 consecutive lines
           Ex: [[[1,2], [3,4]], # line 1 passes through point [1,2] and [3,4]
                [[5,6], [7,8]],
                [[9,10], [11,12]],
                [[13,14], [15,16]]]
    Compute: The intersection between each consecutive lines
             If the intersection falls outside the image, it is projected on the image
    Return: A new contour with the 4 line intersections/the 4 new corners
            Ex: array([[[3, 0]],
                      [[3, 3]],
                      [[0, 3]],
                      [[0, 0]]], dtype=int32)
    """
    c = [0, 1, 2, 3, 0]
    new_contour = []

    assert len(pts) == 4, 'There are more than 4 points in the input list'

    for corner in range(4):
        # First line
        p1 = pts[c[corner]]
        l1 = line(p1[0], p1[1])

        # Second line
        p2 = pts[c[corner + 1]]
        l2 = line(p2[0], p2[1])

        # Find intersection
        inter = intersection(l1, l2)
        assert inter, 'could not find any intersection between 2 lines'

        # Projection on the image
        inter = [max(0, min(ncols, inter[0])), max(0, min(nrows, inter[1]))]

        new_contour.append([inter])

    new_contour = np.array(new_contour, dtype="int32")

    return new_contour


#   /------------------------------------------------/
#  /                   Warping                      /
# /------------------------------------------------/


def warping(img, pts, new_size=500):
    """
    example pts = [[1170,200], [3760,100], [3890,2700], [1250,2800]]
    coordinates are ordered such that the first entry in the list is the top-left,
      the second entry is the top-right, the third is the bottom-right,
    and the fourth is the bottom-left
    """

    # compute the perspective transform matrix
    dst = np.array([
        [0, 0],
        [0, new_size],
        [new_size, new_size],
        [new_size, 0]], dtype="float32")

    m = cv2.getPerspectiveTransform(pts, dst)

    # apply the transformation matrix
    warped = cv2.warpPerspective(img, m, (new_size, new_size))

    # return
    return warped
