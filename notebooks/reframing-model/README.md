# Reframing model

## Context
In order to automate the preparation of images before analysis, we needed to:

* Train a model to detect the region of interest (the quadrat)
* Automatically reframe the image to the ROI

## 1. Quadrat detection

## Steps and Tools
1. **Images annotion** 
   
    Images were manually annotated using the annotation tool `labelme` [^1]

[^1]: [Github: labelme](https://github.com/wkentaro/labelme) 

1. **Data augmentation** 
   
   We used the python library `albumentation` [^2] to perform the data augmentation. You can look at [this documentation](../augmentation/Why_is_albumentation_better.md) for more information.

[^2]: [Github: Albumentation library](https://github.com/albumentations-team/albumentations)

2. **Images and annotation files organization**

    All images were associated to a corresponding .d2json file and organized as follow:
```
./data/
├── training
│   ├── E2B_01_2008.jpg
│   ├── E2B_01_2008.d2json
│   ├── Takapoto_12_2022.jpg
│   ├── Takapoto_12_2022.d2json
│   ├── ...
│   └── Tubuai_20_2018.d2json
└── testing
    ├── E2B_11_2010.jpg
    ├── E2B_11_2010.d2json
    ├── Takapoto_16_2002.jpg
    ├── Takapoto_16_2002.d2json
    ├── ...
    └── Tubuai_01_2005.d2json
```

Example of annotation file: 
```json
{
    "annotations": [
        {
            "bbox": [834, 153, 2761, 2012],
            "bbox_mode": 0,
            "category_id": 0,
            "segmentation": [[2755, 2011, 935, 1985, 834, 159, 2760, 153]]
        }
    ],
    "file_name": "E2B_01_2016.jpg",
    "height": 2050,
    "width": 3139,
    "image_id": 12 
}
```

4. **Training:** 
   
   Finally, we used the notebook [`Detectron2_CoralReef_quadrat.ipynb`](Detectron2_CoralReef_quadrat.ipynb) to train the model on Google Colab.

## 2. Image reframing

The reframing method is based on the model we trained before and on the `warping functions` of OpenCV. [^3]

You can test the reframing pipeline with the notebook [`demo_image_reframing.ipynb`](demo_image_reframing.ipynb)

[^3]: [OpenCV documentation - Image Warping](https://docs.opencv.org/3.4/db/d29/group__cudawarping.html)