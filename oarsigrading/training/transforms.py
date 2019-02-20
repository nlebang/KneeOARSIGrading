import copy
from functools import partial
import numpy as np
import solt.core as slc
import solt.transforms as slt
from torchvision import transforms
import torch

from oarsigrading.kvs import GlobalKVS

import cv2
import solt.data as sld


def wrap2solt(inp_data):
    img, entry = inp_data
    if entry.SIDE == 1:  # Left
        img = cv2.flip(img, 1)

    data_c_content = (img, entry.XRKL, entry.XROSTL, entry.XROSFL, entry.XRJSL, entry.XROSTM, entry.XROSFM, entry.XRJSM)

    dc = sld.DataContainer(data_c_content, 'ILLLLLLL')

    return dc


def unpack_solt_data(dc: sld.DataContainer):
    return dc.data


def apply_by_index(items, transform, idx=0):
    """Applies callable to certain objects in iterable using given indices.
    Parameters
    ----------
    items: tuple or list
    transform: callable
    idx: int or tuple or or list None
    Returns
    -------
    result: tuple
    """
    if idx is None:
        return items
    if not isinstance(items, (tuple, list)):
        raise TypeError
    if not isinstance(idx, (int, tuple, list)):
        raise TypeError

    if isinstance(idx, int):
        idx = [idx, ]

    idx = set(idx)
    res = []
    for i, item in enumerate(items):
        if i in idx:
            res.append(transform(item))
        else:
            res.append(copy.deepcopy(item))

    return res


def normalize_channel_wise(tensor, mean, std):
    if len(tensor.size()) != 3:
        raise ValueError

    for channel in range(tensor.size(0)):
        tensor[channel, :, :] -= mean[channel]
        tensor[channel, :, :] /= std[channel]

    return tensor


def pack_tensors(res):
    img_res, kl, ostl, osfl, jsl, ostm, osfm, jsm = res
    to_tensor = transforms.ToTensor()
    img_res = to_tensor(img_res)
    grades = torch.LongTensor(np.round([kl, ostl, osfl, jsl, ostm, osfm, jsm]).astype(int)).unsqueeze(0)

    return img_res, grades


def init_transforms(mean_vector, std_vector):
    kvs = GlobalKVS()

    if mean_vector is not None:
        mean_vector = torch.from_numpy(mean_vector).float()
        std_vector = torch.from_numpy(std_vector).float()
        norm_trf = partial(normalize_channel_wise, mean=mean_vector, std=std_vector)
        norm_trf = partial(apply_by_index, transform=norm_trf, idx=0)
    else:
        norm_trf = None

    train_trf = [
        wrap2solt,
        slc.Stream([
            slt.PadTransform(pad_to=(kvs['args'].imsize, kvs['args'].imsize)),
            slt.CropTransform(crop_size=(kvs['args'].imsize, kvs['args'].imsize), crop_mode='c'),
            slt.ResizeTransform((kvs['args'].inp_size, kvs['args'].inp_size)),
            slt.ImageAdditiveGaussianNoise(p=0.5, gain_range=0.3),
            slt.RandomRotate(p=1, rotation_range=(-10, 10)),
            slt.CropTransform(crop_size=(kvs['args'].crop_size, kvs['args'].crop_size), crop_mode='r'),
            slt.ImageGammaCorrection(p=0.5, gamma_range=(0.5, 1.5)),
        ]),
        unpack_solt_data,
        pack_tensors,
    ]

    val_trf = [
        wrap2solt,
        slc.Stream([
            slt.PadTransform(pad_to=(kvs['args'].imsize, kvs['args'].imsize)),
            slt.CropTransform(crop_size=(kvs['args'].imsize, kvs['args'].imsize), crop_mode='c'),
            slt.ResizeTransform((kvs['args'].inp_size, kvs['args'].inp_size)),
            slt.CropTransform(crop_size=(kvs['args'].crop_size, kvs['args'].crop_size), crop_mode='c'),
        ]),
        unpack_solt_data,
        pack_tensors,
    ]

    if norm_trf is not None:
        train_trf.append(norm_trf)
        val_trf.append(norm_trf)

    train_trf = transforms.Compose(train_trf)
    val_trf = transforms.Compose(val_trf)

    return train_trf, val_trf
