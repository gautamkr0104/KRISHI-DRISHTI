"""
KRISHI-DRISHTI: Edge AI Model Training & Quantization Pipeline
--------------------------------------------------------------
Author: Bharadwaj (Class 9, CBSE Science Exhibition 2026-27)
Architecture: MobileNetV3-Small (Transfer Learning + INT8 Quantization)
Target Hardware: Samsung Galaxy A03 (Unisoc T606 SoC, Offline Inference)
Dataset: PlantVillage Agricultural Leaf Disease Dataset
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
    print("    Install it via: pip install tensorflow tensorflowjs\n")
    exit(1)

IMAGE_SIZE = (128, 128)
BATCH_SIZE = 32
EPOCHS = 15
NUM_CLASSES = 6

def build_model(num_classes=NUM_CLASSES):
    """
    Constructs an ultra-lightweight MobileNetV3 model optimized for mobile edge inference.
    """
    print(f"\n[+] Building MobileNetV3-Small backbone for {num_classes} classes...")
    base_model = MobileNetV3Small(
        input_shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3),
        include_top=False,
        weights='imagenet',
        pooling='avg'
    )
    
    # Freeze initial layers for transfer learning
    base_model.trainable = False

    inputs = tf.keras.Input(shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3))
    # Preprocessing: Scale [-1, 1]
    x = tf.keras.applications.mobilenet_v3.preprocess_input(inputs)
    x = base_model(x, training=False)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(num_classes, activation='softmax')(x)

    model = models.Model(inputs, outputs, name="krishi_drishti_edge_model")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    return model

def export_tflite_quantized(model, output_path="krishi_drishti_model.tflite"):
    """
    Exports a quantized TFLite model (< 3MB) for offline execution on Samsung Galaxy A03.
    """
    print(f"\n[+] Quantizing and converting to TensorFlow Lite: {output_path}...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_model = converter.convert()

    with open(output_path, "wb") as f:
        f.write(tflite_model)
    
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[✓] TFLite model generated successfully! File size: {size_mb:.2f} MB")

def export_tfjs(model, output_dir="tfjs_model"):
    """
    Exports model in TensorFlow.js format for in-browser client-side execution.
    """
    try:
        import tensorflowjs as tfjs
        print(f"\n[+] Exporting to TensorFlow.js: {output_dir}/...")
        tfjs.converters.save_keras_model(model, output_dir)
        print(f"[✓] TFJS model exported for browser execution!")
    except ImportError:
        print("\n[i] tensorflowjs package not found. Skipping tfjs export.")
        print("    Run 'pip install tensorflowjs' if client-side browser export is needed.")

def main():
    parser = argparse.ArgumentParser(description="KRISHI-DRISHTI AI Model Trainer")
    parser.add_argument("--data_dir", type=str, default=None, help="Path to PlantVillage dataset folder")
    parser.add_argument("--epochs", type=int, default=EPOCHS, help="Number of training epochs")
    args = parser.parse_args()

    print("=========================================================")
    print("  KRISHI-DRISHTI :: MobileNetV3 Edge Model Training")
    print("  Open Source Agritech for CBSE Science Exhibition 2026-27")
    print("=========================================================")

    model = build_model(NUM_CLASSES)
    model.summary()

    if args.data_dir and os.path.exists(args.data_dir):
        print(f"\n[+] Loading dataset from: {args.data_dir}...")
        train_ds = tf.keras.utils.image_dataset_from_directory(
            args.data_dir,
            validation_split=0.2,
            subset="training",
            seed=123,
            image_size=IMAGE_SIZE,
            batch_size=BATCH_SIZE,
            label_mode='categorical'
        )
        val_ds = tf.keras.utils.image_dataset_from_directory(
            args.data_dir,
            validation_split=0.2,
            subset="validation",
            seed=123,
            image_size=IMAGE_SIZE,
            batch_size=BATCH_SIZE,
            label_mode='categorical'
        )
        
        print("\n[+] Training model on dataset...")
        model.fit(train_ds, validation_data=val_ds, epochs=args.epochs)
    else:
        print("\n[i] No dataset path provided (--data_dir).")
        print("    Exporting initial base model with pre-trained ImageNet weights...")
        print("    (Ready for fine-tuning as soon as field leaf images are captured).")

    # Export models
    model.save("krishi_drishti_base.h5")
    export_tflite_quantized(model, "krishi_drishti_model.tflite")
    export_tfjs(model, "tfjs_model")

if __name__ == "__main__":
    main()
