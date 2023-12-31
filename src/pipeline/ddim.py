<<<<<<< HEAD
import math
from typing import Union
import math
from typing import Union

import numpy as np
import torch
from tqdm import tqdm

from utils import unnormalize_to_zero_to_one, numpy_to_pil, match_shape, clip
# import matplotlib

# Retrieve concrete beta
def cos_beta_schedule(timesteps, beta_start=0.0, beta_end=0.999, s=0.008):
    steps = timesteps + 1
    x = torch.linspace(0, timesteps, steps, dtype=torch.float32)
    # s as normalization, prevent 0
    alpha_cumprod = torch.cos(((x / timesteps) + s) / (s + 1) * math.pi * 0.5) ** 2
    alpha_cumprod = alpha_cumprod / alpha_cumprod[0]
    betas = 1 - (alpha_cumprod[1:] / alpha_cumprod[:-1])
    
    return torch.clip(betas, beta_start, beta_end)


class DDIMScheduler:
    def __init__(self,
                 num_train_timesteps:int=1000,
                 beta_start=0.0001,
                 beta_end=0.02,
                 beta_schedule="cosine",
                 clip_sample=True,
                 set_alpha_to_one=True
                 ):
        
        if beta_schedule == "linear":
            self.betas = np.linspace(beta_start, beta_end, num_train_timesteps, dtype=np.float32)
        elif beta_schedule == "cosine":
            self.betas = cos_beta_schedule(num_train_timesteps,
                                              beta_start=beta_start,
                                              beta_end=beta_end)
        else:
            raise NotImplementedError(
                f"{beta_schedule} does is not implemented for {self.__class__}")
        
        self.num_train_timesteps = num_train_timesteps
        self.clip_sample =  clip_sample
        self.alphas = 1.0 - self.betas
        self.alphas_cumprod = np.cumprod(self.alphas, axis=0)
        self.final_alpha = np.array(1.) if set_alpha_to_one else self.alphas_cumprod[0]
        self.num_inference_steps = None
        self.timesteps = np.arange(0, num_train_timesteps)[::-1].copy()
    
    def variance(self, timestep, prev_timestep):
        pa = self.alphas_cumprod[timesteps]
        pa_prev = self.alphas_cumprod[prev_timestep] if prev_timestep >= 0 else self.final_alpha
        ba = 1 - pa
        ba_prev = 1 - pa_prev
        return (ba_prev / ba) * (1 - pa / pa_prev) 
    
    def set_timesteps(self, num_inference_steps, offset=0):
        self.num_inference_steps = num_inference_steps
        self.timesteps = np.arange(0, self.num_train_timesteps, self.num_train_timesteps // num_inference_steps)[::-1].copy()
        self.timesteps += offset
        return None
        
    def step(   self,
                model_output: Union[torch.FloatTensor, np.ndarray],
                timestep: int, 
                sample: Union[torch.FloatTensor, np.ndarray],
                theta: float = 1.0,
                use_clipped_model_output: bool = True,
                generator = None,
                prev_time: bool = False):
        # get previous state
        prev_timestep = timestep - self.num_train_timesteps // self.num_inference_timesteps
        # alpha and betas
        pa = self.alphas_cumprod[timestep]
        pa_prev = self.alphas_cumprod[prev_timestep] if prev_timestep >= 0 else self.final_alpha
        
        ba = 1 - pa
        o
        # x0
        x0 = (sample - ba ** 0.5 * model_output) / pa ** 0.5
        
        if self.clip_sample: 
            x0 = clip(x0, -1, 1)
        
        # get standard deviation
        std_t =  self.variance(self, timestep, prev_timestep) ** 0.5 *  eta
        
        if use_clipped_model_output:
            # re-computed from clipped x0
            model_output = (sample - pa ** (0.5) * x0) / ba ** (0.5)
        
        L_prev = (1 - pa_prev - std_t ** 2) ** (0.5) * model_output
        
        # skip delta * z for simplicity :))))
        x_prev = pa_prev ** (0.5) * x0 + L_prev
        
        if theta > 0:
            device = model_output.device if torch.is_tensor(model_output) else "cpu"
            noise = torch.randn(model_output.shape, generator=generator).to(device)
            V = self.variance(self, timestep, prev_timestep)
            
            if not torch.is_tensor(model_output):
                 V = V.numpy()
            x_prev = x_sample + V * theta
        
        if prev_time is True:
            return x_prev, prev_timestep
        return x_prev
    
    def add_noise(self, original_samples, noise, timesteps):
        if torch.is_tensor(timesteps):
            timesteps = timesteps.cpu()
        
        print(timesteps)
        rpa = match_shape(self.alphas_cumprod[timesteps] ** 0.5, original_samples)
        rba = match_shape((1 - self.alphas_cumprod[timesteps]) ** 0.5, original_samples)
        # print(rpa, rba)
        return rpa * original_samples + rba * noise
    
    @torch.no_grad()
    def generate(self,
                 model, 
                 batch_size=1,
                 generator=None,
                 eta=1.,
                 use_clipped_model_output=True,
                 num_inference_steps=50,
                 output_type="pil",
                 device=None):
        
        device = "cpu" if device is None else device
        img = torch.randn(( batch_size, 
                            model.in_channels, 
                            model.sample_size,
                            model.sample_size), generator=generator)
        img = img.to(device)
        
        self.set_timesteps(num_inference_steps)
        
        for t in tqdm(self.timesteps):
            # compute noise parallely
            model_output = model(img, t)["sample"]
            # predict previous mean + eta V
            img = self.step(model_output, 
                            t,
                            img, 
                            eta,
                            use_clipped_model_output=use_clipped_model_output)
            
            img = unnormalize_to_zero_to_one(img)
            # b rgb
            img_cpu = img.cpu().permute(0, 2, 3, 1).numpy()
            
            if output_type == "pil"
                img_cpu = numpy_to_pil(img_cpu)
            
            return {"sample": img_cpu, "sample_py": img}
    
    def __len__(self) -> int:
        return self.num_train_timesteps

import cv2
if  __name__ == "__main__":
        ddim = DDIMScheduler()
        ddim.set_timesteps(50)
        
        imgs = np.zeros((16, 28, 28, 3))
        
        texture = "This is a an the lmao bruh bruh test duck to the apes tho ty pois".strip().split()
        for i in range(len(texture)):
            cv2.putText(imgs[i, :, :, :], texture[i], (0, 28), cv2.FONT_HERSHEY_SIMPLEX, 1, (1, 1, 1), 2)
            
        imgs = imgs.transpose((0, 3, 1, 2))
        imgs = torch.from_numpy(imgs)
        # timestamp = ddim.num_inference_steps - torch.ones(16, dtype=int) - 1
        timestamp = ddim.num_inference_steps - torch.randint(ddim.num_inference_steps, (16, )) - 1
        # timestamp = torch.ones(16, dtype=int)
        print(timestamp)
        # print(ddim.timesteps)
        noisy_imgs = ddim.add_noise(imgs, torch.randn(16, 3, 28, 28), torch.from_numpy(ddim.timesteps[timestamp])).numpy()
        # imgs = imgs.transpose((0, 2, 3, 1)).astype(int).astype(np.uint8)
        imgs = np.interp(noisy_imgs, (-1, 1), (0, 255)).astype(int).astype(np.uint8).transpose((0, 2, 3, 1)).reshape(-1, 28, 3)
        print(imgs.shape)
        cv2.imwrite("/work/hpc/potato/laos_vi/logs/trash/abstract.jpg", imgs)
        
        
=======
import math
from typing import Union
import math
from typing import Union

import numpy as np
import torch
from tqdm import tqdm

from utils import unnormalize_to_zero_to_one, numpy_to_pil, match_shape, clip
# import matplotlib

# Retrieve concrete beta
def cos_beta_schedule(timesteps, beta_start=0.0, beta_end=0.999, s=0.008):
    steps = timesteps + 1
    x = torch.linspace(0, timesteps, steps, dtype=torch.float32)
    # s as normalization, prevent 0
    alpha_cumprod = torch.cos(((x / timesteps) + s) / (s + 1) * math.pi * 0.5) ** 2
    alpha_cumprod = alpha_cumprod / alpha_cumprod[0]
    betas = 1 - (alpha_cumprod[1:] / alpha_cumprod[:-1])
    
    return torch.clip(betas, beta_start, beta_end)


class DDIMScheduler:
    def __init__(self,
                 num_train_timesteps:int=1000,
                 beta_start=0.0001,
                 beta_end=0.02,
                 beta_schedule="cosine",
                 clip_sample=True,
                 set_alpha_to_one=True
                 ):
        
        if beta_schedule == "linear":
            self.betas = np.linspace(beta_start, beta_end, num_train_timesteps, dtype=np.float32)
        elif beta_schedule == "cosine":
            self.betas = cos_beta_schedule(num_train_timesteps,
                                              beta_start=beta_start,
                                              beta_end=beta_end)
        else:
            raise NotImplementedError(
                f"{beta_schedule} does is not implemented for {self.__class__}")
        
        self.num_train_timesteps = num_train_timesteps
        self.clip_sample =  clip_sample
        self.alphas = 1.0 - self.betas
        self.alphas_cumprod = np.cumprod(self.alphas, axis=0)
        self.final_alpha = np.array(1.) if set_alpha_to_one else self.alphas_cumprod[0]
        self.num_inference_steps = None
        self.timesteps = np.arange(0, num_train_timesteps)[::-1].copy()
    
    def variance(self, timestep, prev_timestep):
        pa = self.alphas_cumprod[timesteps]
        pa_prev = self.alphas_cumprod[prev_timestep] if prev_timestep >= 0 else self.final_alpha
        ba = 1 - pa
        ba_prev = 1 - pa_prev
        return (ba_prev / ba) * (1 - pa / pa_prev) 
    
    def set_timesteps(self, num_inference_steps, offset=0):
        self.num_inference_steps = num_inference_steps
        self.timesteps = np.arange(0, self.num_train_timesteps, self.num_train_timesteps // num_inference_steps)[::-1].copy()
        self.timesteps += offset
        return None
        
    def step(   self,
                model_output: Union[torch.FloatTensor, np.ndarray],
                timestep: int, 
                sample: Union[torch.FloatTensor, np.ndarray],
                theta: float = 1.0,
                use_clipped_model_output: bool = True,
                generator = None,
                prev_time: bool = False):
        # get previous state
        prev_timestep = timestep - self.num_train_timesteps // self.num_inference_timesteps
        # alpha and betas
        pa = self.alphas_cumprod[timestep]
        pa_prev = self.alphas_cumprod[prev_timestep] if prev_timestep >= 0 else self.final_alpha
        
        ba = 1 - pa
        o
        # x0
        x0 = (sample - ba ** 0.5 * model_output) / pa ** 0.5
        
        if self.clip_sample: 
            x0 = clip(x0, -1, 1)
        
        # get standard deviation
        std_t =  self.variance(self, timestep, prev_timestep) ** 0.5 *  eta
        
        if use_clipped_model_output:
            # re-computed from clipped x0
            model_output = (sample - pa ** (0.5) * x0) / ba ** (0.5)
        
        L_prev = (1 - pa_prev - std_t ** 2) ** (0.5) * model_output
        
        # skip delta * z for simplicity :))))
        x_prev = pa_prev ** (0.5) * x0 + L_prev
        
        if theta > 0:
            device = model_output.device if torch.is_tensor(model_output) else "cpu"
            noise = torch.randn(model_output.shape, generator=generator).to(device)
            V = self.variance(self, timestep, prev_timestep)
            
            if not torch.is_tensor(model_output):
                 V = V.numpy()
            x_prev = x_sample + V * theta
        
        if prev_time is True:
            return x_prev, prev_timestep
        return x_prev
    
    def add_noise(self, original_samples, noise, timesteps):
        if torch.is_tensor(timesteps):
            timesteps = timesteps.cpu()
        
        print(timesteps)
        rpa = match_shape(self.alphas_cumprod[timesteps] ** 0.5, original_samples)
        rba = match_shape((1 - self.alphas_cumprod[timesteps]) ** 0.5, original_samples)
        # print(rpa, rba)
        return rpa * original_samples + rba * noise
    
    @torch.no_grad()
    def generate(self,
                 model, 
                 batch_size=1,
                 generator=None,
                 eta=1.,
                 use_clipped_model_output=True,
                 num_inference_steps=50,
                 output_type="pil",
                 device=None):
        
        device = "cpu" if device is None else device
        img = torch.randn((batch_size, 
                             model.in_channels, 
                             model.sample_size,
                             model.sample_size), generator=generator)
        img = img.to(device)
        
        self.set_timesteps(num_inference_steps)
        
        for t in tqdm(self.timesteps):
            # compute noise parallely
            model_output = model(img, t)["sample"]
            # predict previous mean + eta V
            img = self.step(model_output, 
                            t,
                            img, 
                            eta,
                            use_clipped_model_output=use_clipped_model_output)
            
            img = unnormalize_to_zero_to_one(img)
            # b rgb
            img_cpu = img.cpu().permute(0, 2, 3, 1).numpy()
            
            if output_type == "pil":
                img_cpu = numpy_to_pil(img_cpu)
            
            return {"sample": img_cpu, "sample_py": img}
    
    def __len__(self) -> int:
        return self.num_train_timesteps

import cv2
if  __name__ == "__main__":
        ddim = DDIMScheduler()
        ddim.set_timesteps(50)
        
        imgs = np.zeros((16, 28, 28, 3))
        
        texture = "This is a an the lmao bruh bruh test duck to the apes tho ty pois".strip().split()
        for i in range(len(texture)):
            cv2.putText(imgs[i, :, :, :], texture[i], (0, 28), cv2.FONT_HERSHEY_SIMPLEX, 1, (1, 1, 1), 2)
            
        imgs = imgs.transpose((0, 3, 1, 2))
        imgs = torch.from_numpy(imgs)
        # timestamp = ddim.num_inference_steps - torch.ones(16, dtype=int) - 1
        timestamp = ddim.num_inference_steps - torch.randint(ddim.num_inference_steps, (16, )) - 1
        # timestamp = torch.ones(16, dtype=int)
        print(timestamp)
        # print(ddim.timesteps)
        noisy_imgs = ddim.add_noise(imgs, torch.randn(16, 3, 28, 28), torch.from_numpy(ddim.timesteps[timestamp])).numpy()
        # imgs = imgs.transpose((0, 2, 3, 1)).astype(int).astype(np.uint8)
        imgs = np.interp(noisy_imgs, (-1, 1), (0, 255)).astype(int).astype(np.uint8).transpose((0, 2, 3, 1)).reshape(-1, 28, 3)
        print(imgs.shape)
        cv2.imwrite("/work/hpc/potato/laos_vi/logs/trash/abstract.jpg", imgs)
        
        
>>>>>>> 24a4e32af21da811b950f6697a8d410e45e443ac
        