# Random noise for Photo, made at random.
import math
import random
from torchvision import transforms as T
from torchvision.transforms import (
    functional as TF,
    InterpolationMode,
)
import torch
from nunif.utils.perlin2d import generate_perlin_noise_2d
from nunif.utils import blend as B


def random_crop(x, size):
    i, j, h, w = T.RandomCrop.get_params(x, size)
    x = TF.crop(x, i, j, h, w)
    return x


def random_mask_8x8(x, noise):
    assert x.shape == noise.shape
    h = x.shape[1] // 8 + 1
    w = x.shape[2] // 8 + 1
    p = random.uniform(0.02, 0.3)
    mask = torch.bernoulli(torch.torch.full((1, h, w), p))
    method = random.choice([0, 1, 2])
    if method == 0:
        mask = TF.resize(mask, (mask.shape[1] * 8, mask.shape[2] * 8),
                         interpolation=InterpolationMode.NEAREST, antialias=True)
    elif method == 1:
        mask = TF.resize(mask, (mask.shape[1] * 2, mask.shape[2] * 2),
                         interpolation=InterpolationMode.NEAREST, antialias=True)
        mask = TF.resize(mask, (mask.shape[1] * 4, mask.shape[2] * 4),
                         interpolation=InterpolationMode.BILINEAR, antialias=True)
    elif method == 2:
        mask = TF.resize(mask, (mask.shape[1] * 4, mask.shape[2] * 4),
                         interpolation=InterpolationMode.NEAREST, antialias=True)
        mask = TF.resize(mask, (mask.shape[1] * 2, mask.shape[2] * 2),
                         interpolation=InterpolationMode.BILINEAR, antialias=True)
    mask = mask[:, :x.shape[1], :x.shape[2]]
    if random.choice([True, False]):
        mask = mask * torch.bernoulli(torch.torch.full((1, mask.shape[1], mask.shape[2]), 0.5))
    return torch.clamp(x * (1. - mask) + noise * mask, 0., 1.)


def gaussian_noise(x, strength=0.05):
    c, h, w = x.shape
    ch = 1 if random.uniform(0., 1.) < 0.5 else 3
    noise = torch.randn((ch, h, w))
    return torch.clamp(x + noise.expand(x.shape) * strength, 0., 1.)


def gaussian_8x8_masked_noise(x, strength=0.05):
    """
    I don't know what kind of noise this is,
    but it happens in old digital photos.
    (buggy JPEG encoder?)
    """
    c, h, w = x.shape
    method = random.choice([0, 1, 2])
    noise = torch.randn((1, h, w))
    noise = x + noise.expand(x.shape) * strength
    return random_mask_8x8(x, noise)


def sampling_noise(x, sampling=8, strength=0.1):
    c, h, w = x.shape
    noise = (torch.randn((sampling, h, w)) + 0.5).mean(dim=0, keepdim=True)
    m = random.choice([0, 1, 2, 3])
    if m == 0:
        return torch.clamp(B.lighten(x, x + noise.expand(x.shape) * strength), 0., 1.)
    elif m == 1:
        return torch.clamp(B.darken(x, x + noise.expand(x.shape) * strength), 0., 1.)
    elif m == 2:
        return torch.clamp(x + B.multiply(x, noise.expand(x.shape)) * strength, 0., 1.)
    elif m == 3:
        return torch.clamp(x + B.screen(x, noise.expand(x.shape)) * strength, 0., 1.)


def grain_noise1(x, strength=0.1):
    c, h, w = x.shape
    alpha = [1., random.uniform(0, 1)]
    random.shuffle(alpha)
    ch = 1 if random.uniform(0., 1.) < 0.5 else 3
    noise1 = torch.randn((ch, h, w))
    noise2 = torch.randn((ch, h // 2, w // 2))
    interpolation = random.choice([InterpolationMode.BILINEAR, InterpolationMode.NEAREST])
    noise2 = TF.resize(noise2, (h, w),
                       interpolation=interpolation, antialias=True)
    noise = noise1 * alpha[0] + noise2 * alpha[1]
    max_v = torch.abs(noise).max() + 1e-6
    noise = noise / max_v
    return torch.clamp(x + noise.expand(x.shape) * strength, 0., 1.)


def grain_noise2(x, strength=0.3):
    c, h, w = x.shape
    size = max(w, h)
    antialias = random.choice([True, False])
    interpolation = random.choice([InterpolationMode.BILINEAR, InterpolationMode.NEAREST])
    use_rotate = random.choice([True, False])
    if use_rotate:
        bs = math.ceil(size * math.sqrt(2))
        res = random.choice([1, 2])
        ps = bs // res
        ps += 4 - ps % 4
        ns = ps * res * 2
        noise = generate_perlin_noise_2d([ns, ns], [ps, ps]).unsqueeze(0)
        noise = TF.rotate(noise, angle=random.randint(0, 360), interpolation=interpolation)
        noise = TF.center_crop(noise, (int(noise.shape[1] / math.sqrt(2)), int(noise.shape[2] / math.sqrt(2))))
        scale = random.uniform(1., noise.shape[1] / size)
        crop_h = int(h * scale)
        crop_w = int(w * scale)
    else:
        bs = size
        res = random.choice([1, 2])
        ps = bs // res
        ps += 4 - ps % 4
        ns = ps * res * 2
        noise = generate_perlin_noise_2d([ns, ns], [ps, ps]).unsqueeze(0)
        keep_aspect = random.uniform(0, 1) < 0.8
        if keep_aspect:
            scale = random.uniform(1., noise.shape[1] / size)
            crop_h = int(h * scale)
            crop_w = int(w * scale)
        else:
            scale_h = random.uniform(1., noise.shape[1] / size)
            scale_w = random.uniform(1., noise.shape[1] / size)
            crop_h = int(h * scale_h)
            crop_w = int(w * scale_w)

    noise = ((noise + 1.) * 0.5)
    noise = random_crop(noise, (crop_h, crop_w))
    noise = TF.resize(noise, (h, w), interpolation=interpolation, antialias=antialias)
    return torch.clamp(x + noise.expand(x.shape) * strength, 0., 1.)


NR_RATE = {
    0: 0.1,
    1: 0.1,
    2: 0.2,
    3: 0.4,
}
STRENGTH_FACTOR = {
    0: 0.25,
    1: 0.5,
    2: 1.0,
    3: 1.0,
}


class RandomPhotoNoiseX():
    def __init__(self, noise_level, force=False):
        assert noise_level in {0, 1, 2, 3}
        self.noise_level = noise_level
        self.force = force

    def __call__(self, x, y):
        if not self.force:
            if random.uniform(0, 1) > NR_RATE[self.noise_level]:
                # do nothing
                return x, y

        x = TF.to_tensor(x)
        method = random.choice([0, 1, 2, 3])
        if method == 0:
            strength = random.uniform(0.02, 0.1) * STRENGTH_FACTOR[self.noise_level]
            x = sampling_noise(x, strength=strength)
        elif method == 1:
            strength = random.uniform(0.02, 0.1) * STRENGTH_FACTOR[self.noise_level]
            x = grain_noise1(x, strength=strength)
        elif method == 2:
            strength = random.uniform(0.05, 0.2) * STRENGTH_FACTOR[self.noise_level]
            x = grain_noise2(x, strength=strength)
        elif method == 3:
            if random.choice([True, False]):
                strength = random.uniform(0.01, 0.05) * STRENGTH_FACTOR[self.noise_level]
                x = gaussian_noise(x, strength=strength)
            else:
                strength = random.uniform(0.01, 0.05) * STRENGTH_FACTOR[self.noise_level]
                x = gaussian_8x8_masked_noise(x, strength=strength)
        x = TF.to_pil_image(x)
        return x, y


def _test():
    from nunif.utils import pil_io
    import argparse
    import cv2

    def show(name, im):
        cv2.imshow(name, pil_io.to_cv2(im))

    def show_op(func, a):
        show(func.__name__, pil_io.to_image(func(pil_io.to_tensor(a))))

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input", "-i", type=str, required=True, help="input file")
    args = parser.parse_args()
    im, _ = pil_io.load_image_simple(args.input)

    show_op(sampling_noise, im)
    show_op(grain_noise1, im)
    show_op(grain_noise2, im)
    show_op(gaussian_8x8_masked_noise, im)

    cv2.waitKey(0)


if __name__ == "__main__":
    _test()
