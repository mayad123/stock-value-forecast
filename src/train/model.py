"""TensorFlow/Keras model for trend (forward-return) regression."""

import tensorflow as tf


def build_model(
    n_features: int,
    units: int = 16,
    dropout_rate: float = 0.3,
    learning_rate: float = 0.001,
) -> tf.keras.Model:
    """
    Build a small MLP for regression (output in [-1, 1] via tanh).
    Input: (batch, n_features). Output: (batch, 1).
    Expects features to be pre-normalized; scaler params saved in run record.
    """
    inp = tf.keras.layers.Input(shape=(n_features,), dtype=tf.float32, name="features")
    x = tf.keras.layers.Dense(units, activation="relu", kernel_initializer="he_normal", name="dense1")(inp)
    x = tf.keras.layers.Dropout(dropout_rate, name="dropout")(x)
    x = tf.keras.layers.Dense(8, activation="relu", name="dense2")(x)
    out = tf.keras.layers.Dense(1, activation="tanh", name="output")(x)
    model = tf.keras.Model(inputs=inp, outputs=out)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss="mse",
        metrics=["mae"],
    )
    return model
