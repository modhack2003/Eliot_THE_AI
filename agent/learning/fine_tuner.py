"""
Model fine-tuning pipeline using successful exploitation patterns
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import json
import os
from pathlib import Path

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
    from datasets import Dataset
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

from ..persistence.database import get_database, Experience
from ..persistence.logger import get_action_logger


@dataclass
class TrainingData:
    """Training data for model fine-tuning"""
    prompt: str
    completion: str
    success: bool
    context: Dict[str, Any]


@dataclass
class FineTuningConfig:
    """Configuration for fine-tuning"""
    model_name: str = "microsoft/DialoGPT-medium"
    max_length: int = 512
    learning_rate: float = 5e-5
    batch_size: int = 4
    num_epochs: int = 3
    warmup_steps: int = 100
    save_steps: int = 500
    eval_steps: int = 500


class ModelFineTuner:
    """Fine-tune models based on successful exploitation patterns"""
    
    def __init__(self, config: FineTuningConfig = None):
        self.config = config or FineTuningConfig()
        self.logger = logging.getLogger("fine_tuner")
        self.action_logger = get_action_logger()
        self.db = None
        
        # Model components
        self.tokenizer = None
        self.model = None
        self.trainer = None
        
        # Training data
        self.training_data = []
        self.validation_data = []
        
        # Fine-tuned model storage
        self.models_dir = Path("fine_tuned_models")
        self.models_dir.mkdir(exist_ok=True)
        
        self.fine_tuning_enabled = TRANSFORMERS_AVAILABLE
    
    async def initialize(self):
        """Initialize the fine-tuner"""
        if not self.fine_tuning_enabled:
            self.logger.warning("Transformers library not available. Fine-tuning disabled.")
            return
        
        try:
            self.db = await get_database()
            self.logger.info("Model fine-tuner initialized")
        except Exception as e:
            self.logger.error(f"Fine-tuner initialization failed: {e}")
    
    async def start_fine_tuning_loop(self):
        """Start continuous fine-tuning loop"""
        if not self.fine_tuning_enabled:
            return
        
        while True:
            try:
                # Check if we have enough data for fine-tuning
                if await self._should_fine_tune():
                    await self._perform_fine_tuning()
                
                # Wait before next check
                await asyncio.sleep(self.config.save_steps * 10)  # Check every 5000 steps
                
            except Exception as e:
                self.logger.error(f"Fine-tuning loop error: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error
    
    async def _should_fine_tune(self) -> bool:
        """Check if we should perform fine-tuning"""
        try:
            # Get recent experiences
            recent_experiences = await self.db.get_experiences(limit=1000)
            
            # Check if we have enough successful experiences
            successful_experiences = [exp for exp in recent_experiences if exp.success]
            
            # Need at least 100 successful experiences
            return len(successful_experiences) >= 100
            
        except Exception as e:
            self.logger.error(f"Fine-tuning check failed: {e}")
            return False
    
    async def _perform_fine_tuning(self):
        """Perform model fine-tuning"""
        try:
            self.logger.info("Starting model fine-tuning...")
            
            # Prepare training data
            await self._prepare_training_data()
            
            if not self.training_data:
                self.logger.warning("No training data available")
                return
            
            # Load model and tokenizer
            await self._load_model()
            
            # Create datasets
            train_dataset = self._create_dataset(self.training_data)
            val_dataset = self._create_dataset(self.validation_data) if self.validation_data else None
            
            # Set up training arguments
            training_args = self._create_training_arguments()
            
            # Initialize trainer
            self.trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=val_dataset,
                tokenizer=self.tokenizer
            )
            
            # Train model
            self.logger.info("Training model...")
            self.trainer.train()
            
            # Save fine-tuned model
            await self._save_fine_tuned_model()
            
            # Log fine-tuning completion
            self.action_logger.log_learning(
                "fine_tuning",
                self.config.model_name,
                True,
                accuracy=0.8  # Placeholder accuracy
            )
            
            self.logger.info("Model fine-tuning completed")
            
        except Exception as e:
            self.logger.error(f"Fine-tuning failed: {e}")
            self.action_logger.log_learning(
                "fine_tuning",
                self.config.model_name,
                False
            )
    
    async def _prepare_training_data(self):
        """Prepare training data from experiences"""
        try:
            # Get recent experiences
            recent_experiences = await self.db.get_experiences(limit=2000)
            
            self.training_data = []
            self.validation_data = []
            
            for exp in recent_experiences:
                # Create training example
                training_example = await self._create_training_example(exp)
                
                if training_example:
                    # Split into train/validation (80/20)
                    if len(self.training_data) < len(recent_experiences) * 0.8:
                        self.training_data.append(training_example)
                    else:
                        self.validation_data.append(training_example)
            
            self.logger.info(f"Prepared {len(self.training_data)} training examples and {len(self.validation_data)} validation examples")
            
        except Exception as e:
            self.logger.error(f"Training data preparation failed: {e}")
    
    async def _create_training_example(self, experience: Experience) -> Optional[TrainingData]:
        """Create training example from experience"""
        try:
            # Create prompt based on context
            prompt = self._create_prompt_from_context(experience.context)
            
            # Create completion based on action and result
            completion = self._create_completion_from_experience(experience)
            
            if prompt and completion:
                return TrainingData(
                    prompt=prompt,
                    completion=completion,
                    success=experience.success,
                    context=experience.context
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Training example creation failed: {e}")
            return None
    
    def _create_prompt_from_context(self, context: Dict[str, Any]) -> str:
        """Create prompt from experience context"""
        try:
            # Extract relevant information from context
            target_info = context.get("target_info", {})
            vulnerability_info = context.get("vulnerability_info", {})
            scan_results = context.get("scan_results", {})
            
            prompt_parts = []
            
            # Add target information
            if target_info:
                prompt_parts.append(f"Target: {target_info.get('ip', 'unknown')}")
                if target_info.get('os'):
                    prompt_parts.append(f"OS: {target_info['os']}")
                if target_info.get('services'):
                    services = [f"{s.get('service', 'unknown')}:{s.get('port', 'unknown')}" for s in target_info['services']]
                    prompt_parts.append(f"Services: {', '.join(services)}")
            
            # Add vulnerability information
            if vulnerability_info:
                prompt_parts.append(f"Vulnerability: {vulnerability_info.get('type', 'unknown')}")
                if vulnerability_info.get('severity'):
                    prompt_parts.append(f"Severity: {vulnerability_info['severity']}")
            
            # Add scan results
            if scan_results:
                prompt_parts.append(f"Ports open: {scan_results.get('open_ports', 'unknown')}")
            
            # Create final prompt
            prompt = "Given the following target information, what should be the next action?\n\n" + "\n".join(prompt_parts)
            
            return prompt
            
        except Exception as e:
            self.logger.error(f"Prompt creation failed: {e}")
            return ""
    
    def _create_completion_from_experience(self, experience: Experience) -> str:
        """Create completion from experience"""
        try:
            # Create completion based on action and success
            if experience.success:
                completion = f"SUCCESS: {experience.action} on {experience.target}"
                if experience.result:
                    completion += f" - {experience.result}"
            else:
                completion = f"FAILED: {experience.action} on {experience.target}"
                if experience.error:
                    completion += f" - Error: {experience.error}"
            
            return completion
            
        except Exception as e:
            self.logger.error(f"Completion creation failed: {e}")
            return ""
    
    async def _load_model(self):
        """Load model and tokenizer"""
        try:
            self.logger.info(f"Loading model: {self.config.model_name}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )
            
            # Resize token embeddings if needed
            self.model.resize_token_embeddings(len(self.tokenizer))
            
            self.logger.info("Model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Model loading failed: {e}")
            raise
    
    def _create_dataset(self, data: List[TrainingData]):
        """Create Hugging Face dataset from training data"""
        try:
            if not TRANSFORMERS_AVAILABLE:
                self.logger.warning("Transformers not available, skipping dataset creation")
                return None
                
            # Prepare data for tokenization
            texts = []
            for item in data:
                # Combine prompt and completion
                full_text = f"{item.prompt}\n{item.completion}"
                texts.append(full_text)
            
            # Tokenize texts
            tokenized = self.tokenizer(
                texts,
                truncation=True,
                padding=True,
                max_length=self.config.max_length,
                return_tensors="pt"
            )
            
            # Create dataset
            dataset = Dataset.from_dict({
                "input_ids": tokenized["input_ids"],
                "attention_mask": tokenized["attention_mask"],
                "labels": tokenized["input_ids"]  # For causal LM, labels are same as input_ids
            })
            
            return dataset
            
        except Exception as e:
            self.logger.error(f"Dataset creation failed: {e}")
            return None
    
    def _create_training_arguments(self):
        """Create training arguments"""
        try:
            if not TRANSFORMERS_AVAILABLE:
                self.logger.warning("Transformers not available, skipping training arguments")
                return None
                
            return TrainingArguments(
                output_dir=str(self.models_dir / "training_output"),
                num_train_epochs=self.config.num_epochs,
                per_device_train_batch_size=self.config.batch_size,
                per_device_eval_batch_size=self.config.batch_size,
                warmup_steps=self.config.warmup_steps,
                weight_decay=0.01,
                logging_dir=str(self.models_dir / "logs"),
                logging_steps=100,
                save_steps=self.config.save_steps,
                eval_steps=self.config.eval_steps,
                evaluation_strategy="steps" if self.validation_data else "no",
                save_total_limit=3,
                load_best_model_at_end=True if self.validation_data else False,
                metric_for_best_model="eval_loss" if self.validation_data else None,
                greater_is_better=False if self.validation_data else None,
                learning_rate=self.config.learning_rate,
                fp16=torch.cuda.is_available(),
                dataloader_pin_memory=torch.cuda.is_available(),
            )
            
        except Exception as e:
            self.logger.error(f"Training arguments creation failed: {e}")
            raise
    
    async def _save_fine_tuned_model(self):
        """Save fine-tuned model"""
        try:
            # Create model directory
            model_name = f"pentesting_agent_{int(time.time())}"
            model_dir = self.models_dir / model_name
            model_dir.mkdir(exist_ok=True)
            
            # Save model and tokenizer
            self.model.save_pretrained(str(model_dir))
            self.tokenizer.save_pretrained(str(model_dir))
            
            # Save training metadata
            metadata = {
                "model_name": self.config.model_name,
                "training_examples": len(self.training_data),
                "validation_examples": len(self.validation_data),
                "training_time": time.time(),
                "config": self.config.__dict__
            }
            
            metadata_file = model_dir / "training_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"Fine-tuned model saved to: {model_dir}")
            
        except Exception as e:
            self.logger.error(f"Model saving failed: {e}")
            raise
    
    async def load_fine_tuned_model(self, model_path: str):
        """Load a fine-tuned model"""
        try:
            if not os.path.exists(model_path):
                self.logger.error(f"Model path does not exist: {model_path}")
                return False
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # Load model
            self.model = AutoModelForCausalLM.from_pretrained(model_path)
            
            self.logger.info(f"Fine-tuned model loaded from: {model_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Fine-tuned model loading failed: {e}")
            return False
    
    async def generate_response(self, prompt: str) -> str:
        """Generate response using fine-tuned model"""
        try:
            if not self.model or not self.tokenizer:
                self.logger.warning("No fine-tuned model loaded")
                return ""
            
            # Tokenize input
            inputs = self.tokenizer.encode(prompt, return_tensors="pt")
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_length=inputs.shape[1] + 100,
                    num_return_sequences=1,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode response
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Extract only the generated part
            generated_part = response[len(prompt):].strip()
            
            return generated_part
            
        except Exception as e:
            self.logger.error(f"Response generation failed: {e}")
            return ""
    
    async def get_training_statistics(self) -> Dict[str, Any]:
        """Get training statistics"""
        try:
            stats = {
                "fine_tuning_enabled": self.fine_tuning_enabled,
                "training_examples": len(self.training_data),
                "validation_examples": len(self.validation_data),
                "model_loaded": self.model is not None,
                "tokenizer_loaded": self.tokenizer is not None
            }
            
            # Get available models
            available_models = []
            for model_dir in self.models_dir.iterdir():
                if model_dir.is_dir() and (model_dir / "config.json").exists():
                    available_models.append(model_dir.name)
            
            stats["available_models"] = available_models
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Training statistics failed: {e}")
            return {}


# Global fine-tuner instance
fine_tuner_instance = None


async def get_fine_tuner(config: FineTuningConfig = None) -> ModelFineTuner:
    """Get or create fine-tuner instance"""
    global fine_tuner_instance
    
    if fine_tuner_instance is None:
        fine_tuner_instance = ModelFineTuner(config)
        await fine_tuner_instance.initialize()
    
    return fine_tuner_instance
