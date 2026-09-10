import numpy as np
import cv2

# 1) Load the .npz (allow_pickle=True for the 'images' array)
data = np.load("demos/0.npz", allow_pickle=True)

# 2) Inspect which keys you have
print("Keys:", data.files)

# 3) Pull out the images and joint names
images          = data["images_0"]           # shape (N,), each element is an H×W×3 ndarray
joint_names     = data["arm_joint_names"]  # shape (J,)

# 4) Other state arrays
arm_q           = data["arm_q"]            # shape (N, J)
arm_dq          = data["arm_dq"]           # shape (N, J)
ee_pose         = data["ee_pose"]          # shape (N, 7) [tx,ty,tz,qx,qy,qz,qw]
vision_in_body  = data["vision_in_body"]   # shape (N, 7)
body_vel        = data["body_vel"]         # shape (N, 6)
gripper         = data["gripper"]          # shape (N, 1)
ee_force        = data["ee_force"]         # shape (N, 3)
timestamps      = data["t"]                # shape (N, 1)

print("Shape of images:", images[0].shape)
print("Joint names:", joint_names[0])
print("Shape of arm_q:", arm_q.shape)
print("Shape of arm_dq:", arm_dq.shape)
print("Shape of ee_pose:", ee_pose[0])

# 5) Example: display the first frame
# cv2.imshow("First hand camera frame", images[0].astype(np.uint8))
# cv2.waitKey(0)
# cv2.destroyAllWindows()
