from __future__ import division
import warnings

from Networks.HR_Net.seg_hrnet import get_seg_model
from typing import Any, Dict
import torch.nn as nn
import torch.nn.functional as F
from torchvision import datasets, transforms
import dataset
import math
#from runtime import platform
from image import *
from utils import *
import colorama
import logging

from config import return_args, args

warnings.filterwarnings('ignore')
import time

logger = logging.getLogger('mnist_AutoML')

print(args)
img_transform = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
tensor_transform = transforms.ToTensor()

Parameters = Dict[str, Any]
def main(args):
    model = get_seg_model()
    model = nn.DataParallel(model, device_ids=[0])
    model = model.cuda()

    if args.pre:
        if os.path.isfile(args.pre):
            print("=> loading checkpoint '{}'".format(args.pre))
            checkpoint = torch.load(args.pre)
            model.load_state_dict(checkpoint['state_dict'], strict=False)
            args.start_epoch = checkpoint['epoch']
            args.best_pred = checkpoint['best_prec1']
        else:
            print("=> no checkpoint found at '{}'".format(args.pre))

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    #fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')

    #cap = cv2.VideoCapture(args.video_path)
    cap= cv2.VideoCapture(gstreamer_pipeline(flip_method=0), cv2.CAP_GSTREAMER)

    ret, frame = cap.read()
    print(frame.shape)

    '''out video'''
    width = frame.shape[1] #output size
    height = frame.shape[0] #output size
    out = cv2.VideoWriter('./demo.avi', fourcc, 30, (width, height))

    while True:
        try:
            ret, frame = cap.read()

            scale_factor = 0.5
            frame = cv2.resize(frame, (0, 0), fx=scale_factor, fy=scale_factor)
            ori_img = frame.copy()
        except:
            print("test end")
            cap.release()
            break
        frame = frame.copy()
        image = tensor_transform(frame)
        image = img_transform(image).unsqueeze(0)

        with torch.no_grad():
            d6 = model(image)

            count, pred_kpoint = counting(d6)
            point_map = generate_point_map(pred_kpoint)
            box_img = generate_bounding_boxes(pred_kpoint, frame)
            show_fidt = show_fidt_func(d6.data.cpu().numpy())
            #res = np.hstack((ori_img, show_fidt, point_map, box_img))
            res1 = np.hstack((ori_img, show_fidt))
            res2 = np.hstack((box_img, point_map))
            res = np.vstack((res1, res2))

            cv2.putText(res, "Count:" + str(count), (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imwrite('./demo.jpg', res)
            '''write in out_video'''
            out.write(res)
        
        
        cv2.imshow("dst",res)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        print("pred:%.3f" % count)
    cv2.destroyAllWindows()

def gstreamer_pipeline(
    capture_width=1280,
    capture_height=720,
    display_width=1280,
    display_height=720,
    framerate=60,
    flip_method=0,
):
    return (
        "nvarguscamerasrc ! "
        "video/x-raw(memory:NVMM), "
        "width=(int)%d, height=(int)%d, "
        "format=(string)NV12, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )


def counting(input):
    input_max = torch.max(input).item()
    keep = nn.functional.max_pool2d(input, (3, 3), stride=1, padding=1)
    keep = (keep == input).float()
    input = keep * input

    input[input < 100.0 / 255.0 * torch.max(input)] = 0
    input[input > 0] = 1

    '''negative sample'''
    if input_max<0.1:
        input = input * 0

    count = int(torch.sum(input).item())

    kpoint = input.data.squeeze(0).squeeze(0).cpu().numpy()

    return count, kpoint


def generate_point_map(kpoint):
    rate = 1
    pred_coor = np.nonzero(kpoint)
    point_map = np.zeros((int(kpoint.shape[0] * rate), int(kpoint.shape[1] * rate), 3), dtype="uint8") + 255  # 22
    # count = len(pred_coor[0])
    coord_list = []
    for i in range(0, len(pred_coor[0])):
        h = int(pred_coor[0][i] * rate)
        w = int(pred_coor[1][i] * rate)
        coord_list.append([w, h])
        cv2.circle(point_map, (w, h), 3, (0, 0, 0), -1)

    return point_map


def generate_bounding_boxes(kpoint, Img_data):
    '''generate sigma'''
    pts = np.array(list(zip(np.nonzero(kpoint)[1], np.nonzero(kpoint)[0])))
    leafsize = 2048
        
    if pts.shape[0] > 0: # Check if there is a human presents in the frame
        # build kdtree
        tree = scipy.spatial.KDTree(pts.copy(), leafsize=leafsize)

        distances, locations = tree.query(pts, k=4)
        for index, pt in enumerate(pts):
            pt2d = np.zeros(kpoint.shape, dtype=np.float32)
            pt2d[pt[1], pt[0]] = 1.
            if np.sum(kpoint) > 1:
                sigma = (distances[index][1] + distances[index][2] + distances[index][3]) * 0.1
            else:
                sigma = np.average(np.array(kpoint.shape)) / 2. / 2.  # case: 1 point
            sigma = min(sigma, min(Img_data.shape[0], Img_data.shape[1]) * 0.04)

            if sigma < 6:
                t = 2
            else:
                t = 2
            Img_data = cv2.rectangle(Img_data, (int(pt[0] - sigma), int(pt[1] - sigma)),
                                    (int(pt[0] + sigma), int(pt[1] + sigma)), (0, 255, 0), t)

    return Img_data


def show_fidt_func(input):
    input[input < 0] = 0
    input = input[0][0]
    fidt_map1 = input
    fidt_map1 = fidt_map1 / np.max(fidt_map1) * 255
    fidt_map1 = fidt_map1.astype(np.uint8)
    fidt_map1 = cv2.applyColorMap(fidt_map1, 2)
    return fidt_map1

def merge_parameter(base_params, override_params):
    """
    Update the parameters in ``base_params`` with ``override_params``.
    Can be useful to override parsed command line arguments.

    Parameters
    ----------
    base_params : namespace or dict
        Base parameters. A key-value mapping.
    override_params : dict or None
        Parameters to override. Usually the parameters got from ``get_next_parameters()``.
        When it is none, nothing will happen.

    Returns
    -------
    namespace or dict
        The updated ``base_params``. Note that ``base_params`` will be updated inplace. The return value is
        only for convenience.
    """
    if override_params is None:
        return base_params
    is_dict = isinstance(base_params, dict)
    for k, v in override_params.items():
        if is_dict:
            if k not in base_params:
                raise ValueError('Key \'%s\' not found in base parameters.' % k)
            if type(base_params[k]) != type(v) and base_params[k] is not None:
                raise TypeError('Expected \'%s\' in override parameters to have type \'%s\', but found \'%s\'.' %
                                (k, type(base_params[k]), type(v)))
            base_params[k] = v
        else:
            if not hasattr(base_params, k):
                raise ValueError('Key \'%s\' not found in base parameters.' % k)
            if type(getattr(base_params, k)) != type(v) and getattr(base_params, k) is not None:
                raise TypeError('Expected \'%s\' in override parameters to have type \'%s\', but found \'%s\'.' %
                                (k, type(getattr(base_params, k)), type(v)))
            setattr(base_params, k, v)
    return base_params


def get_next_parameter() -> Parameters:
 
    global _params
    _params = platform.get_next_parameter()
    if _params is None:
        return None  # type: ignore
    return _params['parameters']
def get_next_parameter2():
    warning_message = ''.join([
        colorama.Style.BRIGHT,
        colorama.Fore.RED,
        'Running trial code without runtime. ',
        'Please check the tutorial if you are new to NNI: ',
        colorama.Fore.YELLOW,
        'https://nni.readthedocs.io/en/stable/tutorials/hpo_quickstart_pytorch/main.html',
        colorama.Style.RESET_ALL
    ])
    warnings.warn(warning_message, RuntimeWarning)
    return {
        'parameter_id': None,
        'parameters': {}
    }
class AverageMeter(object):
    """Computes and stores the average and current value"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


if __name__ == '__main__':
    #tuner_params = get_next_parameter2()
    #logger.debug(tuner_params)
    #params = vars(merge_parameter(return_args, tuner_params))
    params = return_args  
    print(params)

    main(params)
