import pandas as pd
import numpy as np

# Load data - skip the first 2 rows which contain metadata
#df = pd.read_csv(r"\\wsl.localhost\Ubuntu\home\tpowers\_Code\ferm_process_version_json_builder\04\04\pH_SP_Upper (pH) 8EA855121317829769C0A66647B370F781B602F0.all.csv", 
df = pd.read_csv(r"\\wsl.localhost\Ubuntu\home\tpowers\_Code\ferm_process_version_json_builder\example_ramp.csv", 
                 skiprows=2, 
                 names=["time", "pH"])

# Remove any rows that might contain metadata or non-data values
df = df[df["time"].str.contains("2025")]  # Keep only rows with timestamps
df["pH"] = pd.to_numeric(df["pH"], errors="coerce")  # Convert pH to numeric, set errors to NaN
df = df.dropna()  # Remove any NaN values

# Convert time to datetime
df["time"] = pd.to_datetime(df["time"])

# Convert time to seconds since start
df["time_sec"] = (df["time"] - df["time"].iloc[0]).dt.total_seconds()

# Compute slope using numpy gradient
df["slope"] = np.gradient(df["pH"], df["time_sec"])

# Define threshold for flat vs ramp
epsilon = .000001  # pH per second
print(df["slope"].sort_values(ascending=False))
# Label segments
df["segment_type"] = np.where(np.abs(df["slope"]) > epsilon, "flat", "ramp")

# Group consecutive segments
df["segment_id"] = (df["segment_type"] != df["segment_type"].shift()).cumsum()

# Summarize segments
segments = df.groupby("segment_id").agg(
    start_time=("time", "first"),
    end_time=("time", "last"),
    duration_sec=("time_sec", lambda x: x.iloc[-1] - x.iloc[0]),
    mean_slope=("slope", "mean"),
    std_slope=("slope", "std"),
    type=("segment_type", "first")
).reset_index()

# Display results
print("Segment Analysis:")
print("=" * 50)
for _, row in segments.iterrows():
    print(f"Segment {row['segment_id']}: {row['type']}")
    print(f"  Duration: {row['duration_sec']:.2f} seconds")
    print(f"  Mean slope: {row['mean_slope']:.6f} pH/sec")
    print(f"  Std slope: {row['std_slope']:.6f}")
    print(f"  Time range: {row['start_time']} to {row['end_time']}")
    print("-" * 30)

# Optional: Plot the results
import matplotlib.pyplot as plt

plt.figure(figsize=(12, 8))
plt.plot(df["time"], df["pH"], "b-", label="pH", alpha=0.7)

# Color segments
colors = {"flat": "green", "ramp": "red"}
for seg_id, group in df.groupby("segment_id"):
    seg_type = group["segment_type"].iloc[0]
    plt.fill_between(group["time"], group["pH"].min(), group["pH"].max(), 
                    alpha=0.2, color=colors[seg_type], label=f"{seg_type}" if seg_id == 1 else "")

plt.xlabel("Time")
plt.ylabel("pH")
plt.title("pH Time Series with Flat and Ramp Segments")
plt.legend()
plt.grid(True, alpha=0.3)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()