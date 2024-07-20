import os
import shutil
import argparse
from utils.image_processing import preprocess_single_scene, preprocess_multiple_scenes
from utils.files_and_folders import generate_folder
from utils.captionning import generate_metadata

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base_model",
        type=str,
        default="sdxl",
        help='The base model to use. Choose between ["sdxl", "sd15", "animagine"]',
    )
    parser.add_argument(
        "--multi_gpu",
        action="store_true",
    )
    parser.add_argument(
        "--output_path",
        type=str,
        default="checkpoints/outputs/LoRAs",
        help="The output directory where the model predictions and checkpoints will be written.",
    )
    parser.add_argument(
        "--train_bs",
        type=int,
        default=1,
        help="The size of the batch size for training",
    )
    parser.add_argument(
        "--rank",
        type=int,
        default=6,
        help="The rank of the LoRA",
    )

    args, _ = parser.parse_known_args()

    return args

class LoRATrainer:
    def __init__(self):
        self.args = parse_args()
        if self.args.base_model == "sdxl":
            self.diff_path = "checkpoints/diffusers/stabilityai/stable-diffusion-xl-base-1.0"
            self.out_path_ext = "sdxl"
            self.script_name = "train_text_to_image_lora_sdxl"
            self.train_text_enc = "--train_text_encoder"
        elif self.args.base_model == "animagine":
            self.diff_path = "checkpoints/diffusers/cagliostrolab/animagine-xl-3.1"
            self.out_path_ext = "animagine"
            self.script_name = "train_text_to_image_lora_sdxl"
            self.train_text_enc = "--train_text_encoder"
        elif self.args.base_model == "sd15":
            self.diff_path = "checkpoints/diffusers/runwayml/stable-diffusion-v1-5"
            self.out_path_ext = "sd1.5"
            self.script_name = "train_text_to_image_lora"
            self.train_text_enc = ""
        else:
            raise ValueError('Unrecognized base model. Choose between ["sdxl", "sd15", "animagine"]')

        if self.args.multi_gpu:
            self.multi_gpu = "--multi_gpu"
        else:
            self.multi_gpu = ""

        # self.methods = [Methods.RANDOM_SIZE, Methods.JITTER_RANDOM]


    def train_multi_scene(self, path, apply_preprocess=True, store_preprocess=True, unique_folder=False):
        folder = os.path.split(path)[-1]
        if apply_preprocess:
            path = preprocess_multiple_scenes(path, unique_folder=unique_folder)
            generate_metadata(path)
        else:
            store_preprocess = True  # We don't want to erase the original data directory

        output_path = generate_folder(folder, unique_folder=unique_folder)

        os.system(
            f"accelerate launch {self.multi_gpu} models/Trainers/{self.script_name}.py \
                              --pretrained_model_name_or_path={self.diff_path} \
                              --train_data_dir={path} \
                              --rank={self.args.rank} \
                              --mixed_precision='fp16' \
                              --dataloader_num_workers=8 \
                              --train_batch_size={self.args.train_bs} \
                              {self.train_text_enc} \
                              --learning_rate=1e-04 \
                              --lr_scheduler='cosine' \
                              --snr_gamma=5 \
                              --lr_warmup_steps=0 \
                              --output_dir={output_path} \
                              --num_train_epochs=100 \
                              --checkpointing_steps=50 \
                              --resume_from_checkpoint='latest' \
                              --scale_lr")

        if not store_preprocess:
            shutil.rmtree(path)

        return output_path


    def train_single_scene(self, path, apply_preprocess=True, store_preprocess=True, unique_folder=False):
        folder = os.path.split(path)[-1]
        if apply_preprocess:
            path = preprocess_single_scene(path, unique_folder=unique_folder)
            generate_metadata(path)
        else:
            store_preprocess = True  # We don't want to erase the original data directory

        output_path = generate_folder(folder, unique_folder=unique_folder)

        os.system(
            f"accelerate launch {self.multi_gpu} models/Trainers/{self.script_name}.py \
                      --pretrained_model_name_or_path={self.diff_path} \
                      --train_data_dir={path} \
                      --rank={self.args.rank} \
                      --mixed_precision='fp16' \
                      --dataloader_num_workers=8 \
                      --train_batch_size={self.args.train_bs} \
                      {self.train_text_enc} \
                      --learning_rate=1e-04 \
                      --lr_scheduler='cosine' \
                      --snr_gamma=5 \
                      --lr_warmup_steps=0 \
                      --output_dir={output_path} \
                      --num_train_epochs=100 \
                      --checkpointing_steps=50 \
                      --resume_from_checkpoint='latest' \
                      --scale_lr")

        if not store_preprocess:
            shutil.rmtree(path)

        return output_path





