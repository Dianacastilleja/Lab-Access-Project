from typing import Tuple, Union
import math
import cv2
import numpy as np
from PIL import Image
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from facenet_pytorch import MTCNN, InceptionResnetV1
import torch
from torchvision import transforms
import sqlite3
from io import BytesIO

MARGIN = 10  # pixels
ROW_SIZE = 10  # pixels
FONT_SIZE = 1
FONT_THICKNESS = 1
TEXT_COLOR = (255, 0, 0)  # red

resnet = InceptionResnetV1(pretrained='vggface2').eval()

preprocess = transforms.Compose([
    transforms.Resize(160),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
])

def _normalized_to_pixel_coordinates(
    normalized_x: float, normalized_y: float, image_width: int,
    image_height: int) -> Union[None, Tuple[int, int]]:
  """Converts normalized value pair to pixel coordinates."""

  # Checks if the float value is between 0 and 1.
  def is_valid_normalized_value(value: float) -> bool:
    return (value > 0 or math.isclose(0, value)) and (value < 1 or
                                                      math.isclose(1, value))

  if not (is_valid_normalized_value(normalized_x) and
          is_valid_normalized_value(normalized_y)):
    # TODO: Draw coordinates even if it's outside of the image bounds.
    return None
  x_px = min(math.floor(normalized_x * image_width), image_width - 1)
  y_px = min(math.floor(normalized_y * image_height), image_height - 1)
  return x_px, y_px


def visualize(
    image,
    detection_result
) -> np.ndarray:
  """Draws bounding boxes and keypoints on the input image and return it.
  Args:
    image: The input RGB image.
    detection_result: The list of all "Detection" entities to be visualize.
  Returns:
    Image with bounding boxes.
  """
  annotated_image = image.copy()
  height, width, _ = image.shape

  for detection in detection_result.detections:
    # Draw bounding_box
    bbox = detection.bounding_box
    start_point = bbox.origin_x, bbox.origin_y
    end_point = bbox.origin_x + bbox.width, bbox.origin_y + bbox.height
    cv2.rectangle(annotated_image, start_point, end_point, TEXT_COLOR, 3)

    # Draw keypoints
    for keypoint in detection.keypoints:
      keypoint_px = _normalized_to_pixel_coordinates(keypoint.x, keypoint.y,
                                                     width, height)
      color, thickness, radius = (0, 255, 0), 2, 2
      cv2.circle(annotated_image, keypoint_px, thickness, color, radius)

    # Draw label and score
    category = detection.categories[0]
    category_name = category.category_name
    category_name = '' if category_name is None else category_name
    probability = round(category.score, 2)
    result_text = category_name + ' (' + str(probability) + ')'
    text_location = (MARGIN + bbox.origin_x,
                     MARGIN + ROW_SIZE + bbox.origin_y)
    cv2.putText(annotated_image, result_text, text_location, cv2.FONT_HERSHEY_PLAIN,
                FONT_SIZE, TEXT_COLOR, FONT_THICKNESS)

  return annotated_image

def get_largest_bounding_box(image,detection_result):
  annotated_image = image.copy()

  largest_box = None
  largest_area = -1

  for detection in detection_result.detections:
    bbox = detection.bounding_box
    area = bbox.height * bbox.width

    if area > largest_area:
      largest_box = bbox
      largest_area = area

  if not largest_box:
    return

  annotated_image = annotated_image[largest_box.origin_y:(largest_box.origin_y + largest_box.height),
                                    largest_box.origin_x:(largest_box.origin_x + largest_box.width)]
  return annotated_image

def register_face(image):
    base_options = python.BaseOptions(model_asset_path='detector.tflite')
    options = vision.FaceDetectorOptions(base_options=base_options)
    detector = vision.FaceDetector.create_from_options(options)

    detection_result = detector.detect(image)

    image_copy = np.copy(image.numpy_view())

    annotated_image = visualize(image_copy, detection_result)
    main_face = get_largest_bounding_box(image_copy, detection_result)

    # cv2.imwrite("image.jpg", image_copy)
    # cv2.imwrite("main.jpg", main_face)
    # cv2.imwrite("annotated.jpg", annotated_image)

    rgb_main_face = cv2.cvtColor(main_face, cv2.COLOR_BGR2RGB)

    rgb_main_face_image = Image.fromarray(rgb_main_face)
  
    buffer = BytesIO()
    rgb_main_face_image.save(buffer, format='JPEG')
    buffer = buffer.getvalue()
    # print(buffer)
    # rgb_tensor = preprocess(rgb_main_face_image).unsqueeze(0)

    # with torch.no_grad():
    #   embedding = resnet(rgb_tensor)

    return buffer

def is_face_recognized(image, lab_id=-1) -> bool:
    print('run')
    base_options = python.BaseOptions(model_asset_path='detector.tflite')
    options = vision.FaceDetectorOptions(base_options=base_options)
    detector = vision.FaceDetector.create_from_options(options)

    detection_result = detector.detect(image)

    image_copy = np.copy(image.numpy_view())

    annotated_image = visualize(image_copy, detection_result)
    main_face = get_largest_bounding_box(image_copy, detection_result)
  
    conn = sqlite3.connect('thedatabase.db')
  
    curr = conn.cursor()

    curr.execute('''SELECT first_name, facial_id, lab_id FROM LABMEMBER''')
  
    output = curr.fetchall()
    for row in output:
      if row[2] == lab_id:
        if not row[1] == None:
          nparr = np.frombuffer(row[1], np.uint8)
          test_face = cv2.imdecode(nparr, cv2.COLOR_BGR2RGB)
          # rgb_test_face = cv2.cvtColor(test_face, cv2.COLOR_BGR2RGB)

          # tensor = torch.from_numpy(np.frombuffer(test_face, dtype=np.float32))

          # cv2.imwrite("image.jpg", image_copy)
          # cv2.imwrite("main.jpg", main_face)
          # cv2.imwrite("annotated.jpg", annotated_image)

          rgb_main_face = cv2.cvtColor(main_face, cv2.COLOR_BGR2RGB)
          rgb_test_face = cv2.cvtColor(test_face, cv2.COLOR_BGR2RGB)

          rgb_main_face_image = Image.fromarray(rgb_main_face)
          test_face_image = Image.fromarray(rgb_test_face)

          rgb_tensor = preprocess(rgb_main_face_image).unsqueeze(0)
          test_tensor = preprocess(test_face_image).unsqueeze(0)

          with torch.no_grad():
            embedding_1 = resnet(rgb_tensor)
            embedding_2 = resnet(test_tensor)

          distance = (embedding_1 - embedding_2).norm().item()
          print(distance < 0.6)
          if distance < 0.6:
            conn.commit()
            conn.close()
            return (True, row[0])
    conn.commit()
    conn.close()

    return (False, None)