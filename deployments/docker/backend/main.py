import cv2
import rawpy
import os
import conversion
import restoration
import reframing
import segmentation
from datetime import datetime
from fastapi import FastAPI
from PIL import Image
import numpy as np
import pymysql as sql
import pymysql.cursors

app = FastAPI()

#   /------------------------------------------------/
#  /                    Temp Config                 /
# /------------------------------------------------/

# TODO: Refactor to environment variables
INPUT_RAW = "../storage/input/"
DEST_RESTORED = "../storage/output/restored/"
DEST_REFRAMED = "../storage/output/reframed/"
DEST_SEGMENTED = "../storage/output/segmented/"
DEST_MASKS = "../storage/output/masks/"
MODEL_REFRAME = "../storage/models/detectron2-reframe.pth"
MODEL_CLASSIFY = "../storage/models/detectron2-classifier.pth"
DB_HOST = "coral-detector-db"
DB_PORT = 3306
DB_USER = "coral-detector"
DB_PASSWORD = "ilikecorals"
DB_DATABASE = "coraldata"
DB_CURSOR = sql.cursors.DictCursor


#   /------------------------------------------------/
#  /                  Functions                     /
# /------------------------------------------------/

# TODDO: Refactor to module
async def write_to_db(connection, island, year, position, coverage):
    """Writes the output of a segmented image to the database.

    Args:
        connection: A mysql DB connection object
        island: A string
        year: An integer or a string, 4 digits
        position: An integer or a string in the range of 1 to 20
        coverage: A float between 1 and 0 with up to 8 decimal digits
    """

    with connection:
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO coralcoverage 
                (island, year, position, coverage, last_update)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                coverage = VALUES(coverage),
                last_update = VALUES(last_update);
            """
            cursor.execute(sql, (island, year, position, coverage, datetime.now()))
        connection.commit()


#   /------------------------------------------------/
#  /                    Routes                      /
# /------------------------------------------------/

@app.get("/health")
async def health():
    """Simple health check."""
    return {"message": "OK"}


@app.get("/")
async def root():
    """Nobody should ever see this."""
    return {"message": "Nothing here, but hi!"}


@app.post("/store/{path}")
async def store(path):
    """Stores a new image in the file system.

    Triggers conversion from .NEF to .jpg if needed.
    """
    path = f"{INPUT_RAW}{path}"
    if path.split(".")[-1].lower() == "nef":
        path = conversion.nef_to_jpg(path)
    return {"image": path.split("/")[-1]}


@app.post("/restore")
async def restore(path):
    """Triggers the image restoration function."""
    image = np.array(Image.open(path))
    image = restoration.restore_image(image)
    path = path.replace("input", "restored")
    cv2.imwrite(path, image)
    return {"image": path.split("/")[-1]}


@app.post("/reframe")
async def reframe(path):
    """Triggers the image reframing function."""
    image = np.array(Image.open(path))
    image = reframing.reframe(MODEL_REFRAME, image)
    path = path.replace("restored", "reframed")
    cv2.imwrite(path, image)
    return {"image": path.split("/")[-1]}


@app.post("/segment")
async def segment(path):
    """Triggers the image classifier. Writes the resulting
    image with overlay and the binary mask to disk. Also
    writes the detected coral coverage percentage to the DB.
    """
    image = np.array(Image.open(path))
    image, mask, coverage = segmentation.segmentation(MODEL_CLASSIFY, image)
    path = path.replace("reframed", "segmented")
    path2 = path.replace("segmented", "masks")
    cv2.imwrite(path, image)
    cv2.imwrite(path2, mask)

    # Create a DB connection
    db_connection = sql.connect(host=DB_HOST,
                                user=DB_USER,
                                password=DB_PASSWORD,
                                database=DB_DATABASE,
                                cursorclass=DB_CURSOR)

    # Get year-island-location from path
    img_data = path.split("/")[-1].split(".")[0].split("-")
    img_island = img_data[1]
    img_year = img_data[0]
    img_position = img_data[2]

    await write_to_db(db_connection,
                      img_island,
                      img_year,
                      img_position,
                      coverage)

    return {"image": path.split("/")[-1],
            "mask": path2.split("/")[-1]}
