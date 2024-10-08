import argparse
import os
from datas.LoraDataset import LoraDataset
from torch.utils.data import DataLoader
import torch
import torch.nn.functional as F
from diffusers import (
    AutoencoderKL,
    DDPMScheduler,
    StableDiffusionXLPipeline,
    UNet2DConditionModel,
)
from transformers import CLIPTextModel, CLIPTokenizer
from diffusers.optimization import get_scheduler
from peft import LoraConfig, set_peft_model_state_dict
from tqdm.auto import tqdm


def parse_args(input_args=None):
    parser = argparse.ArgumentParser(description="Simple example of a training script.")
    parser.add_argument(
        "--revision",
        type=str,
        default=None,
        required=False,
        help="Revision of pretrained model identifier from huggingface.co/models.",
    )
    parser.add_argument(
        "--variant",
        type=str,
        default=None,
        help="Variant of the model files of the pretrained model identifier from huggingface.co/models, 'e.g.' fp16",
    )
    parser.add_argument(
        "--image_column", type=str, default="image", help="The column of the dataset containing an image."
    )
    parser.add_argument(
        "--validation_prompt",
        type=str,
        default=None,
        help="A prompt that is used during validation to verify that the model is learning.",
    )
    parser.add_argument(
        "--num_validation_images",
        type=int,
        default=4,
        help="Number of images that should be generated during validation with `validation_prompt`.",
    )
    parser.add_argument(
        "--validation_epochs",
        type=int,
        default=1,
        help=(
            "Run fine-tuning validation every X epochs. The validation process consists of running the prompt"
            " `args.validation_prompt` multiple times: `args.num_validation_images`."
        ),
    )
    parser.add_argument(
        "--max_train_samples",
        type=int,
        default=None,
        help=(
            "For debugging purposes or quicker training, truncate the number of training examples to this "
            "value if set."
        ),
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="sd-model-finetuned-lora",
        help="The output directory where the model predictions and checkpoints will be written.",
    )
    parser.add_argument(
        "--cache_dir",
        type=str,
        default=None,
        help="The directory where the downloaded models and datasets will be stored.",
    )
    parser.add_argument("--seed", type=int, default=None, help="A seed for reproducible training.")
    parser.add_argument(
        "--resolution",
        type=int,
        default=1024,
        help=(
            "The resolution for input images, all the images in the train/validation dataset will be resized to this"
            " resolution"
        ),
    )
    parser.add_argument(
        "--center_crop",
        default=False,
        action="store_true",
        help=(
            "Whether to center crop the input images to the resolution. If not set, the images will be randomly"
            " cropped. The images will be resized to the resolution first before cropping."
        ),
    )
    parser.add_argument(
        "--random_flip",
        action="store_true",
        help="whether to randomly flip images horizontally",
    )
    parser.add_argument(
        "--train_batch_size", type=int, default=1, help="Batch size (per device) for the training dataloader."
    )
    parser.add_argument(
        "--max_train_steps",
        type=int,
        default=500,
        help="Total number of training steps to perform.  If provided, overrides num_train_epochs.",
    )
    parser.add_argument("--to_save", action="store_true")
    parser.add_argument("--num_train_epochs", type=int, default=100)
    parser.add_argument(
        "--checkpointing_steps",
        type=int,
        default=150,
        help=(
            "Save a checkpoint of the training state every X updates. These checkpoints can be used both as final"
            " checkpoints in case they are better than the last checkpoint, and are also suitable for resuming"
            " training using `--resume_from_checkpoint`."
        ),
    )
    parser.add_argument(
        "--checkpoints_total_limit",
        type=int,
        default=None,
        help=("Max number of checkpoints to store."),
    )
    parser.add_argument(
        "--resume_from_checkpoint",
        type=str,
        default=None,
        help=(
            "Whether training should be resumed from a previous checkpoint. Use a path saved by"
            ' `--checkpointing_steps`, or `"latest"` to automatically select the last available checkpoint.'
        ),
    )
    parser.add_argument(
        "--gradient_accumulation_steps",
        type=int,
        default=1,
        help="Number of updates steps to accumulate before performing a backward/update pass.",
    )
    parser.add_argument(
        "--gradient_checkpointing",
        action="store_true",
        help="Whether or not to use gradient checkpointing to save memory at the expense of slower backward pass.",
    )
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=1e-4,
        help="Initial learning rate (after the potential warmup period) to use.",
    )
    parser.add_argument(
        "--scale_lr",
        action="store_true",
        default=False,
        help="Scale the learning rate by the number of GPUs, gradient accumulation steps, and batch size.",
    )
    parser.add_argument(
        "--lr_scheduler",
        type=str,
        default="constant",
        help=(
            'The scheduler type to use. Choose between ["linear", "cosine", "cosine_with_restarts", "polynomial",'
            ' "constant", "constant_with_warmup"]'
        ),
    )
    parser.add_argument(
        "--lr_warmup_steps", type=int, default=500, help="Number of steps for the warmup in the lr scheduler."
    )
    parser.add_argument(
        "--snr_gamma",
        type=float,
        default=None,
        help="SNR weighting gamma to be used if rebalancing the loss. Recommended value is 5.0. "
             "More details here: https://arxiv.org/abs/2303.09556.",
    )
    parser.add_argument(
        "--allow_tf32",
        action="store_true",
        help=(
            "Whether or not to allow TF32 on Ampere GPUs. Can be used to speed up training. For more information, see"
            " https://pytorch.org/docs/stable/notes/cuda.html#tensorfloat-32-tf32-on-ampere-devices"
        ),
    )
    parser.add_argument(
        "--dataloader_num_workers",
        type=int,
        default=0,
        help=(
            "Number of subprocesses to use for data loading. 0 means that the data will be loaded in the main process."
        ),
    )
    parser.add_argument(
        "--use_8bit_adam", action="store_true", help="Whether or not to use 8-bit Adam from bitsandbytes."
    )
    parser.add_argument("--adam_beta1", type=float, default=0.9, help="The beta1 parameter for the Adam optimizer.")
    parser.add_argument("--adam_beta2", type=float, default=0.999, help="The beta2 parameter for the Adam optimizer.")
    parser.add_argument("--adam_weight_decay", type=float, default=1e-2, help="Weight decay to use.")
    parser.add_argument("--adam_epsilon", type=float, default=1e-08, help="Epsilon value for the Adam optimizer")
    parser.add_argument("--max_grad_norm", default=1.0, type=float, help="Max gradient norm.")
    parser.add_argument("--push_to_hub", action="store_true", help="Whether or not to push the model to the Hub.")
    parser.add_argument("--hub_token", type=str, default=None, help="The token to use to push to the Model Hub.")
    parser.add_argument(
        "--prediction_type",
        type=str,
        default=None,
        help="The prediction_type that shall be used for training. Choose between 'epsilon' or 'v_prediction' or leave `None`. If left to `None` the default prediction type of the scheduler: `noise_scheduler.config.prediction_type` is chosen.",
    )
    parser.add_argument(
        "--mixed_precision",
        type=str,
        default=None,
        choices=["no", "fp16", "bf16"],
        help=(
            "Whether to use mixed precision. Choose between fp16 and bf16 (bfloat16). Bf16 requires PyTorch >="
            " 1.10.and an Nvidia Ampere GPU.  Default to the value of accelerate config of the current system or the"
            " flag passed with the `accelerate.launch` command. Use this argument to override the accelerate config."
        ),
    )
    parser.add_argument("--local_rank", type=int, default=-1, help="For distributed training: local_rank")
    parser.add_argument("--noise_offset", type=float, default=0, help="The scale of noise offset.")
    parser.add_argument(
        "--rank",
        type=int,
        default=4,
        help=("The dimension of the LoRA update matrices."),
    )
    parser.add_argument("--image_repeats", type=int, default=10, help="Repeat the images in the training set")


    if input_args is not None:
        args, _ = parser.parse_known_args(input_args)
    else:
        args, _ = parser.parse_known_args()

    env_local_rank = int(os.environ.get("LOCAL_RANK", -1))
    if env_local_rank != -1 and env_local_rank != args.local_rank:
        args.local_rank = env_local_rank

    return args


def tokenize_prompt(tokenizer, prompt):
    text_inputs = tokenizer(
        prompt,
        padding="max_length",
        max_length=tokenizer.model_max_length,
        truncation=True,
        return_tensors="pt",
    )
    text_input_ids = text_inputs.input_ids
    return text_input_ids

# Adapted from pipelines.StableDiffusionXLPipeline.encode_prompt
def encode_prompt(text_encoders, tokenizers, prompt,   text_input_ids_list=None):
    prompt_embeds_list = []

    for i, text_encoder in enumerate(text_encoders):
        if tokenizers is not None:
            tokenizer = tokenizers[i]
            text_input_ids = tokenize_prompt(tokenizer, prompt)
        else:
            assert text_input_ids_list is not None
            text_input_ids = text_input_ids_list[i]

        prompt_embeds = text_encoder(
            text_input_ids.to(text_encoder.device), output_hidden_states=True, return_dict=False
        )

        # We are only ALWAYS interested in the pooled output of the final text encoder
        pooled_prompt_embeds = prompt_embeds[0]
        prompt_embeds = prompt_embeds[-1][-2]
        print("prmpt_embeds", prompt_embeds.shape)
        bs_embed, seq_len, _ = prompt_embeds.shape
        print("bs_embed", bs_embed)
        print("seq_len", seq_len)
        prompt_embeds = prompt_embeds.view(bs_embed, seq_len, -1)
        prompt_embeds_list.append(prompt_embeds)

    prompt_embeds = torch.cat(prompt_embeds_list, dim=-1)
    pooled_prompt_embeds = pooled_prompt_embeds.view(bs_embed, -1)
    return prompt_embeds, pooled_prompt_embeds


class LoraTrainerSimpler:
    def __init__(self, config, args):
        self.config = config
        self.args = parse_args(args)

        print("Preparing training")

        # Load the tokenizers
        self.tokenizer_one = CLIPTokenizer.from_pretrained(
            config.diff_path,
            subfolder="tokenizer",
            revision=self.args.revision,
            use_fast=False,
        )
        self.tokenizer_two = CLIPTokenizer.from_pretrained(
            config.diff_path,
            subfolder="tokenizer_2",
            revision=self.args.revision,
            use_fast=False,
        )

        self.text_encoder_one = CLIPTextModel.from_pretrained(self.config.diff_path, subfolder="text_encoder", revision=self.args.revision)
        self.text_encoder_one.requires_grad_(False)
        self.text_encoder_one.to("cuda")
        print("   - first Text Encoder is ready")
        self.text_encoder_two = CLIPTextModel.from_pretrained(self.config.diff_path, subfolder="text_encoder_2", revision=self.args.revision)
        self.text_encoder_two.requires_grad_(False)
        self.text_encoder_two.to("cuda")
        print("   - second Text Encoder is ready")

        self.noise_scheduler = DDPMScheduler.from_pretrained(self.config.diff_path, subfolder="scheduler")
        print("   - Noise Scheduler is ready")

        self.vae = AutoencoderKL.from_pretrained(self.config.diff_path, subfolder="vae",
                                            revision=self.args.revision, variant=self.args.variant)
        self.vae.requires_grad_(False)
        self.vae.to("cuda")
        print("   - VAE is ready")

        self.unet = UNet2DConditionModel.from_pretrained(self.config.diff_path, subfolder="unet", revision=self.args.revision)
        self.unet.requires_grad_(False)
        self.unet.to("cuda")
        print("   - UNet is ready")

    def __prepare_dataloader(self, input):
        ds = LoraDataset(input, [self.tokenizer_one, self.tokenizer_two])
        def collate_fn(examples):
            pixel_values = torch.stack([example["frames"] for example in examples])
            pixel_values = pixel_values.to(memory_format=torch.contiguous_format).float()
            original_sizes = [example["original_sizes"] for example in examples]
            crop_top_lefts = [example["crop_top_lefts"] for example in examples]
            input_ids_one = torch.stack([example["input_ids_one"] for example in examples])
            input_ids_two = torch.stack([example["input_ids_two"] for example in examples])
            return {
                "frames": pixel_values,
                "input_ids_one": input_ids_one,
                "input_ids_two": input_ids_two,
                "original_sizes": original_sizes,
                "crop_top_lefts": crop_top_lefts,
            }

        return DataLoader(ds, shuffle=True, collate_fn=collate_fn,
                          batch_size=self.args.train_batch_size,
                          num_workers=self.args.dataloader_num_workers)

    def __train(self, dataloader, folder):
        args = self.args
        folder = folder if folder is not None else "AnimeInterp"
        print("Preparing training")
        unet_lora_config = LoraConfig(
            r=args.rank,
            lora_alpha=args.rank,
            init_lora_weights="gaussian",
            target_modules=["to_k", "to_q", "to_v", "to_out.0"],
        )
        self.unet.add_adapter(unet_lora_config)
        print("   - Clean LoRA weights are loaded")

        params_to_optimize = list(filter(lambda p: p.requires_grad, self.unet.parameters()))
        optimizer = torch.optim.AdamW(
            params_to_optimize,
            lr=args.learning_rate,
            betas=(args.adam_beta1, args.adam_beta2),
            weight_decay=args.adam_weight_decay,
            eps=args.adam_epsilon,
        )
        print("   - Optimizer is ready")
        lr_scheduler = get_scheduler(
            args.lr_scheduler,
            optimizer=optimizer,
            num_warmup_steps=args.lr_warmup_steps * args.gradient_accumulation_steps,
            num_training_steps=args.max_train_steps * args.gradient_accumulation_steps,
        )
        print("   - LearningRate Scheduler is ready")

        print("Done!\n\nTraining Begins")

        prompt = f"A photo of {folder}"
        for epoch in range(args.num_train_epochs):
            self.unet.train()
            progress_bar = tqdm(total=len(dataloader))
            progress_bar.set_description(f"Epoch {epoch}")
            print("yay")
            for step, batch in enumerate(dataloader):
                print("yay again")

                latents = self.vae.encode(batch["frames"]).latent_dist.sample()
                latents = latents * self.vae.config.scaling_factor
                bs = latents.shape[0]

                noise = torch.randn_like(latents)
                if args.noise_offset:
                    # https://www.crosslabs.org//blog/diffusion-with-offset-noise
                    noise += args.noise_offset * torch.randn(
                        (latents.shape[0], latents.shape[1], 1, 1), device=latents.device
                    )

                timesteps = torch.randint(0, self.noise_scheduler.config.num_train_timesteps,
                                          (bs,), dtype=torch.int64)
                noise = noise.to("cuda")
                timesteps = timesteps.to("cuda")

                noisy_latents = self.noise_scheduler.add_noise(latents, noise, timesteps)


                # time ids
                def compute_time_ids(original_size, crops_coords_top_left):
                    # Adapted from pipeline.StableDiffusionXLPipeline._get_add_time_ids
                    target_size = (args.resolution, args.resolution)

                    add_time_ids = list(original_size + crops_coords_top_left + target_size)
                    add_time_ids = torch.tensor([add_time_ids])
                    add_time_ids = add_time_ids.to("cuda")
                    return add_time_ids

                add_time_ids = torch.cat(
                    [compute_time_ids(s, c) for s, c in zip(batch["original_sizes"], batch["crop_top_lefts"])]
                )

                # Predict the noise residual
                unet_added_conditions = {"time_ids": add_time_ids}
                prompt_embeds, pooled_prompt_embeds = encode_prompt(
                    text_encoders=[self.text_encoder_one, self.text_encoder_two],
                    tokenizers=None,
                    prompt=None,
                    text_input_ids_list=[batch["input_ids_one"], batch["input_ids_two"]],
                )
                unet_added_conditions.update({"text_embeds": pooled_prompt_embeds})

                noise_pred = self.unet(noisy_latents, timesteps, prompt_embeds, added_cond_kwargs=unet_added_conditions, return_dict=False)[0]

                loss = F.mse_loss(noise_pred, noise)
                loss.backward()
                optimizer.step()
                lr_scheduler.step()
                optimizer.zero_grad()

                progress_bar.update(1)
            if args.to_save:
                if (epoch + 1) % self.config.save_models_epochs == 0 or epoch == args.num_training_epochs - 1:
                    pipeline = StableDiffusionXLPipeline(unet=self.unet, scheduler=self.noise_scheduler)
                    pipeline.save_pretrained(self.config.ckpt_path + folder)

        print(f"Training LoRA on {folder} is finished")

    def train_from_tensors(self, tensors, folder):
        dataloader = self.__prepare_dataloader(tensors)
        return self.__train(dataloader, folder)

    def train_from_path(self, path, folder):
        dataloader = self.__prepare_dataloader(path, "images")
        return self.__train(dataloader, folder)
