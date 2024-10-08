prefix = 'D:/University/ForthYear/GuidedProject/atd_12k/'
# testset_root = prefix + 'datasets/test_2k_540p'
# test_flow_root = prefix + 'datasets/test_2k_pre_calc_sgm_flows'
# test_annotation_root = prefix + 'datasets/test_2k_annotations/'

# prefix = 'D:/University/ForthYear/GuidedProject/other_animations'
prefix = 'Datasets_root/AoT/'
testset_root = prefix + 'full_shots/'
test_flow_root = prefix + 'AoT_sgm_flows/'

test_size = (960, 540)
test_crop_size = (960, 540)
# test_size = (1920, 1080)
# test_crop_size = (1920, 1080)

mean = [0., 0., 0.]
std = [1, 1, 1]
seed = 0

inter_frames = 1

model = 'CannyDiffimeInterp'
pwc_path = None

checkpoint = 'checkpoints/anime_interp_full.ckpt'
diff_path = 'checkpoints/diffusers/stabilityai/stable-diffusion-xl-base-1.0'
controlnet_id = 'checkpoints/diffusers/diffusers/controlnet-canny-sdxl-1.0'

store_path = 'outputs/canny_diffusion'



