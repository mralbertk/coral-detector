# Known Issues & Limitations 
The below issues are known bugs and/or limits of the existing implementation.

### Incorrectly named files cause exceptions
- Only files following the naming convention _integer_._filetype_ can be processed correctly.
- Any file that is not in `.NEF` or `.jpg` can also cause exceptions 

### There is no easy way to delete stuff, even mistakes
- To remove an image from the Docker application, delete it from the `/storage` directory on the host machine
- To remove an image from the AWS application, remove it directly from the affected S3 bucket(s)
- To remove entries from the local database, enter the running mysql container and access the DB directly 
- To remove entries from the Aurora database, access the database directly

### Coral coverage is displayed incorrectly in streamlit
- The dataframe displaying coral coverage in the dockerized web application drops all leading zeroes 
- For example, a coverage of `0.054233` (5.4233%) will display as `54233`
- The .csv export will contain the correct values 
- This does not affect the AWS version where the coral coverage is represented in percent

### Images in the gallery are sorted incorrectly 
- Image are sorted by name as string as `1, 10, 11, ... 19, 2, 3, ... 20`
- This only affects the dockerized version

### The application is terribly slow, especially when processing multiple galleries 
- This only affects the dockerized version
- The best solution is to process images in batches of no more than 20
- The worst idea is to launch a new batch when a batch is still running

### The AWS web interface can crash when pushing too many images 
- This only affects the AWS version and happens when the container runs out of memory
- Avoid this by either limiting total upload batch sizes or increasing the container resources
- The good news: The service recovers automatically
