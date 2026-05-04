#!/usr/bin/env python3
"""Create a plot, upload it to the API, then fetch it back."""

import os
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests


BASE_URL = os.getenv("BASE_URL", " https://stability-armored-friction.ngrok-free.dev")
API_KEY = os.getenv("API_KEY", "test-api-key-12345")


def main() -> None:
    x_values = [0, 1, 2, 3, 4, 5]
    y_values = [0, 1, 4, 9, 16, 25]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        plot_path = temp_path / "plot.png"

        plt.figure(figsize=(8, 5), dpi=150)
        plt.plot(x_values, y_values, marker="o", linewidth=2)
        plt.title("Test Plot")
        plt.xlabel("X Axis")
        plt.ylabel("Y Axis")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(plot_path, format="png")
        plt.close()

        print(f"Created plot: {plot_path}")

        with plot_path.open("rb") as plot_file:
            upload_response = requests.post(
                f"{BASE_URL}/v1/images",
                files={"file": (plot_path.name, plot_file, "image/png")},
                headers={"X-API-Key": API_KEY},
                timeout=30,
            )

        upload_response.raise_for_status()
        upload_data = upload_response.json()
        image_id = upload_data["image_id"]
        image_url = upload_data["image_url"]

        print(f"Uploaded image id: {image_id}")
        print(f"Uploaded image url: {image_url}")


if __name__ == "__main__":
    main()
