import cv2
import os


_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "models",
    "face_detection_yunet_2023mar.onnx",
)


def create_face_detector():
    if not os.path.exists(_MODEL_PATH):
        raise FileNotFoundError(
            f"YuNet model not found: {_MODEL_PATH}"
        )

    return cv2.FaceDetectorYN.create(
        _MODEL_PATH,
        "",
        (640, 640),
        0.75,
        0.3,
        5000,
    )


def detect_faces(video_path, sample_interval=0.5):
    detector = create_face_detector()
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise RuntimeError("Could not open video.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if fps <= 0 or width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError("Invalid video properties.")

    detector.setInputSize((width, height))
    frame_interval = max(1, int(fps * sample_interval))

    detections = []
    frame_number = 0

    while True:
        success, frame = cap.read()
        if not success:
            break

        if frame_number % frame_interval == 0:
            _, faces = detector.detect(frame)
            if faces is not None:
                for face in faces:
                    x, y, w, h = face[:4]
                    confidence = float(face[14])
                    if confidence < 0.75:
                        continue
                    detections.append({
                        "time": round(frame_number / fps, 3),
                        "x": float(x),
                        "y": float(y),
                        "width": float(w),
                        "height": float(h),
                        "center_x": float(x + w / 2),
                        "center_y": float(y + h / 2),
                        "confidence": confidence,
                    })
        frame_number += 1

    cap.release()
    return {
        "video_width": width,
        "video_height": height,
        "fps": fps,
        "detections": detections,
    }


def build_face_tracks(face_data, max_distance=220):
    detections = face_data["detections"]

    if not detections:
        return []

    frames = {}
    for detection in detections:
        timestamp = detection["time"]
        frames.setdefault(timestamp, []).append(detection)

    tracks = []
    next_track_id = 1

    for timestamp in sorted(frames.keys()):
        current_faces = frames[timestamp]

        available_tracks = []
        for track in tracks:
            last_detection = track["observations"][-1]
            time_gap = timestamp - last_detection["time"]
            if time_gap <= 1.5:
                available_tracks.append(track)

        possible_matches = []
        for track in available_tracks:
            last = track["observations"][-1]
            for face_index, face in enumerate(current_faces):
                distance = (
                    (last["center_x"] - face["center_x"]) ** 2
                    + (last["center_y"] - face["center_y"]) ** 2
                ) ** 0.5
                if distance <= max_distance:
                    possible_matches.append(
                        (distance, track, face_index)
                    )

        possible_matches.sort(key=lambda item: item[0])

        used_tracks = set()
        used_faces = set()
        for distance, track, face_index in possible_matches:
            track_id = track["id"]
            if track_id in used_tracks:
                continue
            if face_index in used_faces:
                continue
            track["observations"].append(current_faces[face_index])
            used_tracks.add(track_id)
            used_faces.add(face_index)

        for face_index, face in enumerate(current_faces):
            if face_index in used_faces:
                continue
            tracks.append({
                "id": next_track_id,
                "observations": [face],
            })
            next_track_id += 1

    return tracks


def get_primary_face_track(tracks):
    if not tracks:
        return None
    return max(
        tracks,
        key=lambda track: (
            len(track["observations"]),
            sum(
                face["width"] * face["height"]
                for face in track["observations"]
            ) / len(track["observations"]),
        ),
    )


def smooth_positions(values, window=5):
    if not values:
        return []

    smoothed = []
    for index in range(len(values)):
        start = max(0, index - window // 2)
        end = min(len(values), index + window // 2 + 1)
        nearby = values[start:end]
        smoothed.append(sum(nearby) / len(nearby))
    return smoothed


def get_camera_positions(face_data, track_id=None):
    tracks = build_face_tracks(face_data)

    if not tracks:
        return []

    if track_id is None:
        selected_track = get_primary_face_track(tracks)
    else:
        selected_track = next(
            (
                track for track in tracks
                if track["id"] == track_id
            ),
            None,
        )

    if selected_track is None:
        return []

    observations = selected_track["observations"]
    centers = [face["center_x"] for face in observations]
    smoothed = smooth_positions(centers)

    return [
        {
            "time": face["time"],
            "center_x": center,
        }
        for face, center in zip(observations, smoothed)
    ]


def create_tracking_preview(
    video_path,
    face_data,
    output_path="outputs/face_tracking_preview.mp4",
):
    tracks = build_face_tracks(face_data)

    if not tracks:
        raise RuntimeError("No face tracks found.")

    primary = get_primary_face_track(tracks)
    primary_id = primary["id"]

    observations = []
    for track in tracks:
        for face in track["observations"]:
            observations.append({
                **face,
                "track_id": track["id"],
            })
    observations.sort(key=lambda item: item["time"])

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Could not open video.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(
        output_path,
        fourcc,
        fps,
        (width, height),
    )

    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Could not create preview video.")

    latest_faces = {}
    observation_index = 0
    frame_number = 0

    while True:
        success, frame = cap.read()
        if not success:
            break

        current_time = frame_number / fps
        while (
            observation_index < len(observations)
            and observations[observation_index]["time"] <= current_time
        ):
            face = observations[observation_index]
            latest_faces[face["track_id"]] = face
            observation_index += 1

        for track_id, face in list(latest_faces.items()):
            age = current_time - face["time"]
            if age > 0.8:
                continue

            x = int(face["x"])
            y = int(face["y"])
            w = int(face["width"])
            h = int(face["height"])

            if track_id == primary_id:
                color = (0, 255, 0)
                label = f"PRIMARY ID {track_id}"
            else:
                color = (255, 180, 0)
                label = f"TRACK {track_id}"

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(
                frame,
                label,
                (x, max(25, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                color,
                2,
            )

        writer.write(frame)
        frame_number += 1

    cap.release()
    writer.release()
    return output_path


def score_face_track(track):
    observations = track["observations"]
    if not observations:
        return 0

    count = len(observations)
    duration = (
        observations[-1]["time"] - observations[0]["time"]
    )
    average_area = sum(
        face["width"] * face["height"]
        for face in observations
    ) / count
    average_confidence = sum(
        face["confidence"] for face in observations
    ) / count

    duration_score = min(duration / 30, 1.0)
    detection_score = min(count / 40, 1.0)
    size_score = min(average_area / 20000, 1.0)

    return (
        duration_score * 0.40
        + detection_score * 0.35
        + size_score * 0.15
        + average_confidence * 0.10
    )


def get_best_face_track(tracks):
    if not tracks:
        return None
    return max(tracks, key=score_face_track)


def compare_face_tracks(track_a, track_b):
    import math
    from statistics import median

    a = track_a["observations"]
    b = track_b["observations"]
    if not a or not b:
        return None

    last_a = a[-1]
    first_b = b[0]
    gap = first_b["time"] - last_a["time"]
    if gap < 0:
        return None

    distance = math.sqrt(
        (last_a["center_x"] - first_b["center_x"]) ** 2
        + (last_a["center_y"] - first_b["center_y"]) ** 2
    )
    width_a = median(f["width"] for f in a)
    width_b = median(f["width"] for f in b)
    height_a = median(f["height"] for f in a)
    height_b = median(f["height"] for f in b)

    width_ratio = min(width_a, width_b) / max(width_a, width_b)
    height_ratio = min(height_a, height_b) / max(height_a, height_b)

    return {
        "track_a": track_a["id"],
        "track_b": track_b["id"],
        "gap_seconds": round(gap, 2),
        "distance_pixels": round(distance, 1),
        "width_similarity": round(width_ratio, 2),
        "height_similarity": round(height_ratio, 2),
    }


def find_candidate_track_links(
    tracks,
    max_gap=7.5,
    max_distance=80,
    min_width_similarity=0.85,
    min_height_similarity=0.85,
):
    from statistics import median
    import math

    links = []
    for track_a in tracks:
        for track_b in tracks:
            if track_a["id"] == track_b["id"]:
                continue

            a = track_a["observations"]
            b = track_b["observations"]
            last_a = a[-1]
            first_b = b[0]
            gap = first_b["time"] - last_a["time"]

            if gap <= 0 or gap > max_gap:
                continue

            distance = math.sqrt(
                (last_a["center_x"] - first_b["center_x"]) ** 2
                + (last_a["center_y"] - first_b["center_y"]) ** 2
            )
            width_a = median(f["width"] for f in a)
            width_b = median(f["width"] for f in b)
            height_a = median(f["height"] for f in a)
            height_b = median(f["height"] for f in b)

            width_similarity = (
                min(width_a, width_b) / max(width_a, width_b)
            )
            height_similarity = (
                min(height_a, height_b) / max(height_a, height_b)
            )

            if (
                distance <= max_distance
                and width_similarity >= min_width_similarity
                and height_similarity >= min_height_similarity
            ):
                links.append({
                    "from": track_a["id"],
                    "to": track_b["id"],
                    "gap": round(gap, 2),
                    "distance": round(distance, 1),
                    "width_similarity": round(width_similarity, 2),
                    "height_similarity": round(height_similarity, 2),
                })

    return sorted(
        links,
        key=lambda link: (
            link["distance"],
            -link["width_similarity"],
            -link["height_similarity"],
        ),
    )


def build_track_chains(tracks, links):
    incoming = {}
    outgoing = {}

    sorted_links = sorted(
        links,
        key=lambda link: (
            link["distance"],
            -link["width_similarity"],
            -link["height_similarity"],
        ),
    )

    for link in sorted_links:
        source = link["from"]
        target = link["to"]

        if source in outgoing:
            continue
        if target in incoming:
            continue

        current = source
        creates_cycle = False
        while current in incoming:
            current = incoming[current]
            if current == target:
                creates_cycle = True
                break
        if creates_cycle:
            continue

        outgoing[source] = target
        incoming[target] = source

    chains = []
    visited = set()

    for track in tracks:
        track_id = track["id"]
        if track_id in incoming:
            continue

        chain = []
        current = track_id
        while current is not None and current not in visited:
            chain.append(current)
            visited.add(current)
            current = outgoing.get(current)
        chains.append(chain)

    return chains


def create_chain_tracking_preview(
    video_path,
    tracks,
    chains,
    output_path="outputs/chain_tracking_preview.mp4",
):
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    best_chain = max(
        chains,
        key=lambda chain: sum(
            len(next(
                t["observations"]
                for t in tracks
                if t["id"] == track_id
            ))
            for track_id in chain
        ),
    )

    track_to_chain = {}
    for chain_number, chain in enumerate(chains, start=1):
        for track_id in chain:
            track_to_chain[track_id] = chain_number

    best_chain_number = next(
        number
        for number, chain in enumerate(chains, start=1)
        if chain == best_chain
    )

    observations_by_time = {}
    for track in tracks:
        track_id = track["id"]
        chain_number = track_to_chain[track_id]
        for obs in track["observations"]:
            bucket = round(round(obs["time"] * 2) / 2, 2)
            observations_by_time.setdefault(bucket, []).append({
                "track_id": track_id,
                "chain_number": chain_number,
                "x": int(obs["x"]),
                "y": int(obs["y"]),
                "width": int(obs["width"]),
                "height": int(obs["height"]),
            })

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Could not open input video.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(
        output_path,
        fourcc,
        fps,
        (width, height),
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Could not create tracking preview.")

    frame_number = 0
    while True:
        success, frame = cap.read()
        if not success:
            break

        current_time = frame_number / fps
        bucket = round(round(current_time * 2) / 2, 2)
        observations = observations_by_time.get(bucket, [])

        for obs in observations:
            x = obs["x"]
            y = obs["y"]
            w = obs["width"]
            h = obs["height"]

            if obs["chain_number"] == best_chain_number:
                color = (0, 255, 0)
            else:
                color = (255, 120, 0)

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            label = (
                f"Chain {obs['chain_number']} | "
                f"Track {obs['track_id']}"
            )
            cv2.putText(
                frame,
                label,
                (x, max(20, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

        cv2.putText(
            frame,
            f"Selected Chain: {best_chain_number}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )

        writer.write(frame)
        frame_number += 1

    cap.release()
    writer.release()
    print("Tracking preview saved:", output_path)
    print("Selected face chain:", best_chain)
    return best_chain


def get_chain_camera_positions(tracks, chain, window=5):
    observations = []
    for track_id in chain:
        track = next(
            (t for t in tracks if t["id"] == track_id),
            None,
        )
        if track is None:
            continue
        for obs in track["observations"]:
            observations.append({
                "time": obs["time"],
                "center_x": obs["center_x"],
                "center_y": obs["center_y"],
            })
    observations.sort(key=lambda item: item["time"])

    if not observations:
        return []

    groups = []
    current_group = [observations[0]]
    for obs in observations[1:]:
        gap = obs["time"] - current_group[-1]["time"]
        if gap <= 1.0:
            current_group.append(obs)
        else:
            groups.append(current_group)
            current_group = [obs]
    groups.append(current_group)

    results = []
    for group in groups:
        x_values = [item["center_x"] for item in group]
        y_values = [item["center_y"] for item in group]
        smooth_x = smooth_positions(x_values, window)
        smooth_y = smooth_positions(y_values, window)
        for i, item in enumerate(group):
            results.append({
                "time": round(item["time"], 2),
                "center_x": round(smooth_x[i], 1),
                "center_y": round(smooth_y[i], 1),
            })
    return results


def create_smart_crop_preview(
    video_path,
    positions,
    output_path="outputs/smart_crop_preview.mp4",
):
    """
    Create a 9:16 preview that follows the selected face horizontally.

    When face observations are unavailable, the camera eases back toward
    the center of the original video instead of holding an old position.
    """
    import bisect

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    positions = sorted(positions, key=lambda item: item["time"])
    if not positions:
        raise ValueError("No camera positions available.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open input video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError("Invalid input video properties.")

    crop_width = min(int(height * 9 / 16), width)
    if crop_width <= 0:
        cap.release()
        raise RuntimeError("Could not calculate a valid 9:16 crop.")

    output_width = 1080
    output_height = 1920

    writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (output_width, output_height),
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Could not create output video: {output_path}")

    times = [item["time"] for item in positions]

    camera_x = width / 2
    frame_number = 0
    smoothing_strength = 0.12
    max_hold_distance = 0.75

    try:
        while True:
            success, frame = cap.read()
            if not success:
                break

            current_time = frame_number / fps
            index = bisect.bisect_left(times, current_time)
            target_x = width / 2

            if 0 < index < len(positions):
                before = positions[index - 1]
                after = positions[index]
                gap = after["time"] - before["time"]
                if 0 < gap <= 1.0:
                    fraction = (
                        (current_time - before["time"]) / gap
                    )
                    fraction = max(0.0, min(1.0, fraction))
                    target_x = (
                        before["center_x"] * (1 - fraction)
                        + after["center_x"] * fraction
                    )
                else:
                    nearest = min(
                        (before, after),
                        key=lambda item: abs(item["time"] - current_time),
                    )
                    if abs(nearest["time"] - current_time) <= max_hold_distance:
                        target_x = nearest["center_x"]
            elif index == 0:
                first = positions[0]
                if abs(first["time"] - current_time) <= max_hold_distance:
                    target_x = first["center_x"]
            else:
                last = positions[-1]
                if abs(last["time"] - current_time) <= max_hold_distance:
                    target_x = last["center_x"]

            camera_x += (target_x - camera_x) * smoothing_strength

            left = int(round(camera_x - crop_width / 2))
            left = max(0, min(left, width - crop_width))
            cropped = frame[:, left:left + crop_width]
            resized = cv2.resize(
                cropped,
                (output_width, output_height),
                interpolation=cv2.INTER_AREA,
            )
            writer.write(resized)
            frame_number += 1
    finally:
        cap.release()
        writer.release()

    print("Smart crop preview saved:", output_path)