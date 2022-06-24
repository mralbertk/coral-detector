# Deploy with Docker Compose

## Summary
Deploy the solution on your local machine using Docker.

## Installation & Setup
- Install Docker: https://docs.docker.com/get-docker/
- Clone this repository: `git clone https://github.com/mralbertk/coral-detector`
- Navigate to your local repository and run `docker compose up`

## Required Models
- To successfully deploy the application, you will need:
  - A detectron2 model `detectron2-reframe.pth` trained for reframing in /storage/models
  - A detectron2 model `detectron2-classifier.pth` trained for coral detection in storage/models
- The code to create these models is available in [notebooks](../../notebooks) 
- Unfortunately, we cannot make pre-trained models or labelled datasets for training available

## Use
- The streamlit web application is available at `localhost:8501`
- All processed images and the database are stored via bind mounts in `/storage`
- For general usage instructions, view the top-level [documentation](../../README.md)

## Shutdown 
- To stop the application, run `docker compose down`

## Known Issues & Limitations 
- Refer to the top-level [documentation](../../ISSUES.md)