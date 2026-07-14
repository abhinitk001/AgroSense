import os
import json
import tensorflow as tf

from keras.preprocessing import image_dataset_from_directory
from keras.applications import MobileNetV2
from keras.applications.mobilenet_v2 import preprocess_input
from keras.models import Sequential
from keras.layers import (
    GlobalAveragePooling2D,
    Dense,
    Dropout
)
from keras.callbacks import (
    EarlyStopping,
    ModelCheckpoint
)

# ==========================================================
# SETTINGS
# ==========================================================

DATASET_PATH = "datasets/plant_disease"

MODEL_PATH = "ml/disease_model.keras"

CLASS_PATH = "ml/disease_classes.json"

IMAGE_SIZE = (224, 224)

BATCH_SIZE = 32

EPOCHS = 15

# ==========================================================
# LOAD DATASET
# ==========================================================

print("=" * 60)
print("Loading Dataset...")
print("=" * 60)

train_dataset = image_dataset_from_directory(
    DATASET_PATH,
    validation_split=0.2,
    subset="training",
    seed=42,
    image_size=IMAGE_SIZE,
    batch_size=BATCH_SIZE
)

validation_dataset = image_dataset_from_directory(
    DATASET_PATH,
    validation_split=0.2,
    subset="validation",
    seed=42,
    image_size=IMAGE_SIZE,
    batch_size=BATCH_SIZE
)

# ==========================================================
# CLASS NAMES
# ==========================================================

class_names = train_dataset.class_names

print("\nDisease Classes:\n")

for i, c in enumerate(class_names):
    print(f"{i+1}. {c}")

# Save class names

with open(CLASS_PATH, "w") as f:
    json.dump(class_names, f, indent=4)

# ==========================================================
# PERFORMANCE
# ==========================================================

AUTOTUNE = tf.data.AUTOTUNE

train_dataset = (
    train_dataset
    .cache()
    .shuffle(1000)
    .prefetch(AUTOTUNE)
)

validation_dataset = (
    validation_dataset
    .cache()
    .prefetch(AUTOTUNE)
)

# ==========================================================
# DATA AUGMENTATION
# ==========================================================

data_augmentation = tf.keras.Sequential([

    tf.keras.layers.RandomFlip("horizontal"),

    tf.keras.layers.RandomRotation(0.15),

    tf.keras.layers.RandomZoom(0.20),

    tf.keras.layers.RandomContrast(0.15)

])

# ==========================================================
# LOAD MOBILENETV2
# ==========================================================

print("\nLoading MobileNetV2...\n")

base_model = MobileNetV2(

    input_shape=(224,224,3),

    include_top=False,

    weights="imagenet"

)

base_model.trainable = False

print("MobileNetV2 Loaded Successfully")

# ==========================================================
# BUILD MODEL
# ==========================================================

model = Sequential([

    data_augmentation,

    tf.keras.layers.Rescaling(1./127.5, offset=-1),

    base_model,

    GlobalAveragePooling2D(),

    Dropout(0.30),

    Dense(
        256,
        activation="relu"
    ),

    Dropout(0.20),

    Dense(
        len(class_names),
        activation="softmax"
    )

])

# ==========================================================
# COMPILE
# ==========================================================

model.compile(

    optimizer="adam",

    loss="sparse_categorical_crossentropy",

    metrics=["accuracy"]

)

print("\nModel Summary\n")

model.summary()
# ==========================================================
# CALLBACKS
# ==========================================================

checkpoint = ModelCheckpoint(
    MODEL_PATH,
    monitor="val_accuracy",
    save_best_only=True,
    mode="max",
    verbose=1
)

early_stop = EarlyStopping(
    monitor="val_accuracy",
    patience=5,
    restore_best_weights=True,
    verbose=1
)

# ==========================================================
# TRAIN MODEL
# ==========================================================

print("\n" + "=" * 60)
print("Training Started...")
print("=" * 60)

history = model.fit(
    train_dataset,
    validation_data=validation_dataset,
    epochs=EPOCHS,
    callbacks=[
        checkpoint,
        early_stop
    ]
)

print("\nTraining Completed Successfully!")

# ==========================================================
# EVALUATE MODEL
# ==========================================================

print("\nEvaluating Model...\n")

loss, accuracy = model.evaluate(validation_dataset)

print(f"\nValidation Accuracy : {accuracy*100:.2f}%")
print(f"Validation Loss     : {loss:.4f}")

# ==========================================================
# SAVE MODEL
# ==========================================================

model.save(MODEL_PATH)

print("\n" + "=" * 60)
print("Disease Model Saved Successfully")
print("=" * 60)

print(f"Model : {MODEL_PATH}")
print(f"Classes : {CLASS_PATH}")