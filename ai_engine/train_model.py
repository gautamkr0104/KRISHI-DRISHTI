"""
KRISHI-DRISHTI: High-Accuracy Edge AI Training & Quantization Pipeline
----------------------------------------------------------------------
Author: Bharadwaj (Class 9, CBSE Science Exhibition 2026-27)
Architecture: MobileNetV3-Small (Two-Stage Fine-Tuning + INT8 Quantization)
Target Hardware: Samsung Galaxy A03 (Unisoc T606 SoC, Offline Inference)
Dataset: PlantVillage Agricultural Leaf Disease Dataset (Solanaceae Focus)
Target Accuracy: > 97.5% - 98.5%
"""

import os
import json
import argparse
import numpy as np

# Suppress verbose TensorFlow logs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

try:
    import tensorflow as tf
    from tensorflow.keras import layers, models
    from tensorflow.keras.applications import MobileNetV3Small
except ImportError:
    print("\n[!] TensorFlow is not installed in this Python environment.")
    print("    Install it via: pip install tensorflow\n")
    exit(1)

IMAGE_SIZE = (128, 128)
BATCH_SIZE = 32
WARMUP_EPOCHS = 4
FINE_TUNE_EPOCHS = 6
NUM_CLASSES = 6

def get_data_augmentation():
    """
    Simulates field variations: sunlight angles, hand tremor, leaf orientation.
    """
    return tf.keras.Sequential([
        layers.RandomFlip("horizontal_and_vertical"),
        layers.RandomRotation(0.15),
        layers.RandomZoom(0.1),
        layers.RandomContrast(0.1),
    ], name="canopy_field_augmentation")

def build_model(num_classes=NUM_CLASSES):
    """
    Constructs high-accuracy MobileNetV3-Small backbone with residual dense classifier.
    """
    print(f"\n[+] Building MobileNetV3-Small backbone for {num_classes} classes...")
    base_model = MobileNetV3Small(
        input_shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3),
        include_top=False,
        weights='imagenet',
        pooling='avg'
    )
    
    # Freeze initial layers for warmup
    base_model.trainable = False

    augmentation = get_data_augmentation()

    inputs = tf.keras.Input(shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3), name="leaf_input")
    x = augmentation(inputs)
    x = tf.keras.applications.mobilenet_v3.preprocess_input(x)
    x = base_model(x, training=False)
    
    # Classifier Head with Dropout for regularisation
    x = layers.Dropout(0.25)(x)
    x = layers.Dense(128, activation='relu', name="pathology_dense")(x)
    x = layers.Dropout(0.20)(x)
    outputs = layers.Dense(num_classes, activation='softmax', name="disease_classification")(x)

    model = models.Model(inputs, outputs, name="krishi_drishti_edge_model")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    return model, base_model

def export_tflite_quantized(model, output_path="krishi_drishti_model.tflite"):
    """
    Exports an ultra-compact quantized TFLite model (~1 MB) for offline execution.
    """
    print(f"\n[+] Quantizing and converting to TensorFlow Lite: {output_path}...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_model = converter.convert()

    with open(output_path, "wb") as f:
        f.write(tflite_model)
    
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[OK] TFLite model generated successfully! File size: {size_mb:.2f} MB")

def main():
    parser = argparse.ArgumentParser(description="KRISHI-DRISHTI High-Accuracy AI Trainer")
    parser.add_argument("--data_dir", type=str, default=r"C:\Users\DELL\.cache\plantvillage_solanaceae", help="Path to dataset")
    parser.add_argument("--warmup_epochs", type=int, default=WARMUP_EPOCHS, help="Warmup epochs for classifier head")
    parser.add_argument("--finetune_epochs", type=int, default=FINE_TUNE_EPOCHS, help="Fine-tuning epochs for top layers")
    args = parser.parse_args()

    print("=========================================================")
    print("  KRISHI-DRISHTI :: High-Accuracy MobileNetV3 Training")
    print("  Target Accuracy: > 97-98% (Two-Stage Fine-Tuning)")
    print("  CBSE Science Exhibition 2026-27 Research Architecture")
    print("=========================================================")

    model, base_model = build_model(NUM_CLASSES)

    if args.data_dir and os.path.exists(args.data_dir):
        print(f"\n[+] Loading agricultural dataset from: {args.data_dir}...")
        train_ds = tf.keras.utils.image_dataset_from_directory(
            args.data_dir,
            validation_split=0.2,
            subset="training",
            seed=42,
            image_size=IMAGE_SIZE,
            batch_size=BATCH_SIZE,
            label_mode='categorical'
        )
        val_ds = tf.keras.utils.image_dataset_from_directory(
            args.data_dir,
            validation_split=0.2,
            subset="validation",
            seed=42,
            image_size=IMAGE_SIZE,
            batch_size=BATCH_SIZE,
            label_mode='categorical'
        )

        # Prefetch for max CPU throughput
        train_ds = train_ds.prefetch(buffer_size=tf.data.AUTOTUNE)
        val_ds = val_ds.prefetch(buffer_size=tf.data.AUTOTUNE)

        print(f"\n>>> STAGE 1: Training Classifier Head ({args.warmup_epochs} Warmup Epochs)...")
        model.fit(train_ds, validation_data=val_ds, epochs=args.warmup_epochs)

        print(f"\n>>> STAGE 2: Deep Fine-Tuning Top Layers of MobileNetV3 ({args.finetune_epochs} Epochs)...")
        base_model.trainable = True
        # Freeze initial 35 layers, unfreeze remaining upper convolutional blocks
        for layer in base_model.layers[:-25]:
            layer.trainable = False

        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        history = model.fit(train_ds, validation_data=val_ds, epochs=args.finetune_epochs)
        
        final_acc = history.history['val_accuracy'][-1] * 100
        print(f"\n=========================================================")
        print(f"  [SUCCESS] FINAL VALIDATION ACCURACY: {final_acc:.2f}%")
        print(f"=========================================================")

    else:
        print("\n[!] Dataset directory not found. Please specify valid --data_dir.")

    # Export production models
    model.save("krishi_drishti_base.h5")
    export_tflite_quantized(model, "krishi_drishti_model.tflite")

if __name__ == "__main__":
    main()
