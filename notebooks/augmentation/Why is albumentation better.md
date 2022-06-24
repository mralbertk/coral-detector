





**Data augmentation** is a technique that enables you to significantly increase the diversity of data available for training models, without actually collecting new data.

**Albumentation** is a fast image augmentation library and easy to use with other libraries as a wrapper. The package is written on **NumPy**, **OpenCV**, and **imgaug**. What makes this library different is the number of data augmentation techniques that are available. While most of the augmentation libraries include techniques like cropping, flipping, rotating and scaling, albumentation provides a range of very extensive image augmentation techniques like contrast, blur and channel shuffle. Here is the range of augmentations that can be performed.

### **Why is albumentation better?**

The reason this library gained popularity in a small period of time is because of the features it offers. Some of the reasons why this library is better are:

- **Performance**: Albumentations delivers the best performance on most of the commonly used augmentations. It does this by wrapping several low-level image manipulation libraries and selects the fastest implementation. 
- **Variety:** This library not only contains the common image manipulation techniques but a wide variety of image transforms. This is helpful for the task and domain-specific applications. 
- **Flexibility:** Because this package is fairly new, there are multiple image transformations that are proposed and the package has to undergo these changes. But, albumentation has proven to be quite flexible in research and is easily adaptable to the changes. 





```
class albumentations.augmentations.transforms.Blur` `(blur_limit=7, always_apply=False, p=0.5)
```

Blur the input image using a random-sized kernel.

| `blur_limit` | `int, [int, int]` | maximum kernel size for blurring the input image. Should be in range [3, inf). Default: (3, 7). |
| ------------ | ----------------- | ------------------------------------------------------------ |
| `p`          | `float`           | probability of applying the transform. Default: 0.5.         |

```
transform3 = a.Compose([
    a.Blur(blur_limit=2, p=1),
    a.ChannelShuffle(p=1)], 
    bbox_params=a.BboxParams(format='coco', label_fields=['category_ids']),
    keypoint_params=a.KeypointParams(format='xy'))
```



```
class albumentations.augmentations.transforms.ChannelShuffle
```

Randomly rearrange channels of the input RGB image.

| Name | Type    | Description                                          |
| :--- | :------ | :--------------------------------------------------- |
| `p`  | `float` | probability of applying the transform. Default: 0.5. |



Aug9_SCL_2726 D09.jpg

![](imgs\image-20220624030538665.png)



Aug8_SCL_2726 D09.jpg

![](imgs\image-20220624030638378.png)



Aug7_SCL_2726 D09.jpg

<img src="imgs\image-20220624030801994.png" alt="image-20220624030801994" style="zoom: 50%;" />

![](imgs\image-20220624031001992.png)



Aug4_SCL_2726 D09.jpg

![](imgs\image-20220624031224636.png)
