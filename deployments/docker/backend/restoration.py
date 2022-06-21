import cv2
import numpy as np
import numpy.matlib
import rawpy


def get_dark_channel(img, blockSize=15):
    """Get dark channel for an image.
    @param img: The source image.
    @param size: Patch size.
    @return The dark channel of the image.
    """
    minch = np.amin(img, axis=2)
    box = cv2.getStructuringElement(cv2.MORPH_RECT, (blockSize // 2, blockSize // 2))
    return cv2.erode(minch, box)


def estimate_atmospheric_light(image, jDark):
    """Estimate atmospheric light for an image.
    @param image: The source image.
    @param jDark: Dark channel for an image.
    @return The estimated atmospheric light of the image.
    """
    height, width, channel = image.shape
    numpx = max(int(width * height / 1000), 1)
    jDarkVec = np.reshape(jDark, (width * height))
    imgVec = np.reshape(image, (width * height, channel))
    indices = np.argsort(jDarkVec)
    brightest_indices = indices[width * height - numpx:]
    atmSum = np.zeros(channel)
    for i in range(numpx):
        atmSum = atmSum + imgVec[brightest_indices[i]]
    A = atmSum / numpx
    return A


def estimate_transmission(image, A):
    omega = 0.95
    height, width, channel = image.shape
    img = np.zeros((height, width, channel))
    for c in range(channel):
        img[:, :, c] = image[:, :, c] / float(A[c])
    transmission = 1 - omega * get_dark_channel(img)
    return transmission


def boxfilter(image, r):
    height, width = image.shape[:2]
    dstImage = np.zeros((height, width))

    cumImage = np.cumsum(image, axis=0)
    dstImage[0: r + 1, :] = cumImage[r: 2 * r + 1, :]
    dstImage[r + 1: height - r, :] = cumImage[2 * r + 1: height, :] - cumImage[0: height - 2 * r - 1, :]
    dstImage[height - r: height, :] = \
        np.matlib.repmat(cumImage[height - 1, :], r, 1) - cumImage[height - 2 * r - 1: height - r - 1, :]

    cumImage = np.cumsum(dstImage, axis=1)
    dstImage[:, 0: r + 1] = cumImage[:, r: 2 * r + 1]
    dstImage[:, r + 1: width - r] = cumImage[:, 2 * r + 1: width] - cumImage[:, 0: width - 2 * r - 1]
    dstImage[:, width - r: width] = \
        np.matlib.repmat(np.matrix(cumImage[:, width - 1]).T, 1, r) - cumImage[:, width - 2 * r - 1: width - r - 1]

    return dstImage


def guide_filter(I, p, r, eps):
    height, width = I.shape[:2]
    N = boxfilter(np.ones((height, width)), r)
    mean_I = boxfilter(I, r) / N
    mean_p = boxfilter(p, r) / N
    corr_II = boxfilter(I * I, r) / N
    corr_Ip = boxfilter(I * p, r) / N

    var_I = corr_II - mean_I * mean_I
    cov_Ip = corr_Ip - mean_I * mean_p

    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I

    mean_a = boxfilter(a, r) / N
    mean_b = boxfilter(b, r) / N

    q = mean_a * I + mean_b
    return q


def dehaze(image, A, transmission):
    t0 = 0.1
    height, width, channel = image.shape
    J = np.zeros((height, width, channel))
    for c in range(channel):
        J[:, :, c] = A[c] + (image[:, :, c] - A[c]) / np.maximum(transmission, t0)
    return J


def apply_clahe(image, clipLimit=2.0, tileGridSize=(8, 8)):
    """Apply clahe function from OpenCV on a BGR image
    https://stackoverflow.com/questions/25008458/how-to-apply-clahe-on-rgb-color-images
    """
    # convert BGR to LAB format to be able to apply CLAHE
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lab_planes = list(cv2.split(lab))
    clahe = cv2.createCLAHE(clipLimit, tileGridSize)
    lab_planes[0] = clahe.apply(lab_planes[0])

    # convert back to BGR
    lab = cv2.merge(lab_planes)
    img_clahe = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    return img_clahe


def restore_image(img):
    img = img[:, :, [2, 1, 0]]
    img_dark = get_dark_channel(img)
    atm_light = estimate_atmospheric_light(img, img_dark)
    transmission = estimate_transmission(img, atm_light)
    transmission_refined = guide_filter(transmission, transmission, 3, 0.01)
    img_dehazed = dehaze(img, atm_light, transmission_refined)
    # Disabled until fix
    # img_clahe = apply_clahe(img_dehazed.astype('uint8')*255)
    return img_dehazed


if __name__ == "__main__":
    with rawpy.imread("1.NEF") as raw:
        img = raw.postprocess()
    img = img[:, :, [2, 1, 0]]
    img = restore_image(img)
    cv2.imwrite("1.jpg", img)



