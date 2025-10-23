#!/usr/bin/env python3
"""
Download FLAN-T5 model for development.
"""

import sys
from pathlib import Path


def download_flan_t5(model_size="large"):
    """Download FLAN-T5 model to local cache."""
    models = {
        "base": "google/flan-t5-base",
        "large": "google/flan-t5-large",
        "xl": "google/flan-t5-xl",
    }

    model_name = models[model_size]
    cache_dir = Path("./services/models/flan-t5")
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {model_name} to {cache_dir}...")

    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name, cache_dir=str(cache_dir)
        )
        tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=str(cache_dir))
        print(f"✅ {model_name} downloaded successfully to {cache_dir}")
        return True
    except ImportError:
        print("❌ transformers module not found. Please install it first:")
        print("   pip install transformers torch")
        return False
    except Exception as e:
        print(f"❌ Failed to download {model_name}: {e}")
        return False


if __name__ == "__main__":
    model_size = sys.argv[1] if len(sys.argv) > 1 else "large"
    success = download_flan_t5(model_size)
    sys.exit(0 if success else 1)
