import cv2
import tkinter as tk
from tkinter import Label, Button, Text, Scrollbar, Frame
from PIL import Image, ImageTk
import threading
import queue
import time
import json
import os
from ultralytics import YOLO
import numpy as np

# Try to import ArmLib for DOFBOT control (adjust based on actual library)
try:
    from Arm_Lib import Arm_Device

    DOFBOT_AVAILABLE = True
except ImportError:
    print("Arm_Lib not available. Running in simulation mode.")
    DOFBOT_AVAILABLE = False


    class Arm_Device:
        def __init__(self):
            pass

        def Arm_serial_servo_write(self, *args):
            print(f"Simulated servo move: {args}")

        def Arm_serial_servo_write6(self, *args):
            print(f"Simulated 6-servo move: {args}")


class DOFBOTCameraGUI:
    def __init__(self, window):
        self.window = window
        self.window.title("DOFBOT Camera Detection System")

        # Set window size
        self.window.geometry("1400x900")

        # Initialize DOFBOT Arm
        self.arm = Arm_Device()

        # Load YOLO model
        self.model_path = "models/office_yolo.pt"
        self.load_yolo_model()

        # Custom class names mapping
        self.CUSTOM_NAMES = {
            0: "adapter",
            1: "eraser",
            2: "mouse",
            3: "pen",
            4: "pendrive",
            5: "stapler",
        }

        # Detection threshold
        self.CONF_THRES = 0.5

        # Setup GUI
        self.setup_gui()

        # Initialize variables
        self.cap = None
        self.running = False
        self.detecting = False
        self.frame_queue = queue.Queue(maxsize=2)
        self.detection_queue = queue.Queue(maxsize=2)
        self.last_time = time.time()
        self.frame_count = 0
        self.detected_items = []
        self.scan_positions = []
        self.current_scan_index = 0
        self.scanning = False

        # Predefined scanning positions (angles for servos 1-6)
        self.scan_positions = [
            [90, 90, 90, 90, 90, 90],  # Center position
            [60, 90, 90, 90, 90, 90],  # Left
            [120, 90, 90, 90, 90, 90],  # Right
            [90, 60, 90, 90, 90, 90],  # Up
            [90, 120, 90, 90, 90, 90],  # Down
        ]

        # Start camera automatically
        self.window.after(500, self.start_camera_auto)

    def load_yolo_model(self):
        """Load YOLO model"""
        try:
            print(f"[INFO] Loading YOLO model from: {self.model_path}")
            self.model = YOLO(self.model_path, task="detect")
            print("[INFO] YOLO model loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load YOLO model: {e}")
            self.model = None

    def setup_gui(self):
        """Setup the GUI layout"""
        # Main container
        main_container = Frame(self.window)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Left panel for video
        left_panel = Frame(main_container, width=900)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Video display
        self.video_label = Label(left_panel, bg="black", text="Initializing DOFBOT Camera...",
                                 font=("Arial", 14), fg="white")
        self.video_label.pack(fill="both", expand=True)

        # FPS label
        self.fps_label = Label(left_panel, text="FPS: --", fg="green",
                               font=("Arial", 10))
        self.fps_label.pack(anchor="w", pady=(5, 0))

        # Right panel for controls and logs
        right_panel = Frame(main_container, width=400)
        right_panel.pack(side="right", fill="both", padx=(10, 0))

        # Control frame
        control_frame = LabelFrame(right_panel, text="DOFBOT Controls", font=("Arial", 12, "bold"), padx=10, pady=10)
        control_frame.pack(fill="x", pady=(0, 10))

        # Camera controls
        cam_control_frame = Frame(control_frame)
        cam_control_frame.pack(fill="x", pady=5)

        self.start_btn = Button(cam_control_frame, text="Start Camera", command=self.start_camera,
                                width=15, height=2, bg="green", fg="white",
                                font=("Arial", 10, "bold"))
        self.start_btn.pack(side="left", padx=2)

        self.stop_btn = Button(cam_control_frame, text="Stop Camera", command=self.stop_camera,
                               width=15, height=2, bg="red", fg="white", state="disabled",
                               font=("Arial", 10, "bold"))
        self.stop_btn.pack(side="left", padx=2)

        # Detection controls
        detect_control_frame = Frame(control_frame)
        detect_control_frame.pack(fill="x", pady=5)

        self.detect_btn = Button(detect_control_frame, text="Start Detection", command=self.toggle_detection,
                                 width=15, height=2, bg="blue", fg="white",
                                 font=("Arial", 10, "bold"))
        self.detect_btn.pack(side="left", padx=2)

        self.scan_btn = Button(detect_control_frame, text="Start Scanning", command=self.start_scanning,
                               width=15, height=2, bg="purple", fg="white",
                               font=("Arial", 10, "bold"))
        self.scan_btn.pack(side="left", padx=2)

        # Movement controls
        move_frame = LabelFrame(control_frame, text="Manual Control", font=("Arial", 10))
        move_frame.pack(fill="x", pady=5)

        # Row 1
        row1 = Frame(move_frame)
        row1.pack(pady=2)
        Button(row1, text="↑ Up", command=lambda: self.move_arm(0, 10), width=8).pack(side="left", padx=2)

        # Row 2
        row2 = Frame(move_frame)
        row2.pack(pady=2)
        Button(row2, text="← Left", command=lambda: self.move_arm(-10, 0), width=8).pack(side="left", padx=2)
        Button(row2, text="Center", command=self.center_arm, width=8).pack(side="left", padx=2)
        Button(row2, text="Right →", command=lambda: self.move_arm(10, 0), width=8).pack(side="left", padx=2)

        # Row 3
        row3 = Frame(move_frame)
        row3.pack(pady=2)
        Button(row3, text="↓ Down", command=lambda: self.move_arm(0, -10), width=8).pack(side="left", padx=2)

        # Status frame
        status_frame = LabelFrame(right_panel, text="System Status", font=("Arial", 12, "bold"), padx=10, pady=10)
        status_frame.pack(fill="x", pady=(0, 10))

        self.status_label = Label(status_frame, text="Status: Initializing...", fg="blue",
                                  font=("Arial", 10), anchor="w", justify="left")
        self.status_label.pack(fill="x", pady=2)

        self.detection_status = Label(status_frame, text="Detection: Inactive", fg="orange",
                                      font=("Arial", 10), anchor="w", justify="left")
        self.detection_status.pack(fill="x", pady=2)

        self.arm_status = Label(status_frame, text="DOFBOT: Disconnected", fg="red",
                                font=("Arial", 10), anchor="w", justify="left")
        self.arm_status.pack(fill="x", pady=2)

        # Detection results frame
        results_frame = LabelFrame(right_panel, text="Detection Results", font=("Arial", 12, "bold"), padx=10, pady=10)
        results_frame.pack(fill="both", expand=True)

        # Results text area
        results_text_frame = Frame(results_frame)
        results_text_frame.pack(fill="both", expand=True)

        scrollbar = Scrollbar(results_text_frame)
        scrollbar.pack(side="right", fill="y")

        self.results_text = Text(results_text_frame, height=15, yscrollcommand=scrollbar.set,
                                 font=("Consolas", 9), wrap="word")
        self.results_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.results_text.yview)

        # Clear results button
        Button(results_frame, text="Clear Results", command=self.clear_results,
               width=15, bg="gray", fg="white").pack(pady=(5, 0))

    def start_camera_auto(self):
        """Start camera automatically"""
        print("Auto-starting DOFBOT camera...")
        self.start_camera()

    def start_camera(self):
        """Start the camera stream"""
        if not self.running:
            self.status_label.config(text="Status: Starting camera...", fg="orange")

            # Try to open camera (adjust index as needed for DOFBOT)
            for cam_index in [0, 1, 2]:
                self.cap = cv2.VideoCapture(cam_index)
                if self.cap.isOpened():
                    print(f"Camera found at index {cam_index}")
                    break

            if self.cap and self.cap.isOpened():
                # Set camera properties
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.cap.set(cv2.CAP_PROP_FPS, 30)

                self.running = True
                self.start_btn.config(state="disabled")
                self.stop_btn.config(state="normal")
                self.status_label.config(text="Status: Camera Running", fg="green")
                self.arm_status.config(text=f"DOFBOT: {'Connected' if DOFBOT_AVAILABLE else 'Simulation Mode'}",
                                       fg="green" if DOFBOT_AVAILABLE else "orange")

                # Start camera thread
                self.camera_thread = threading.Thread(target=self.capture_frames, daemon=True)
                self.camera_thread.start()

                # Start GUI update
                self.update_gui()
            else:
                self.status_label.config(text="Status: No camera found", fg="red")
                self.video_label.config(text="No Camera Found\nPlease check DOFBOT connection")

    def stop_camera(self):
        """Stop the camera stream"""
        print("Stopping camera...")
        self.running = False
        self.detecting = False
        self.scanning = False

        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.detect_btn.config(text="Start Detection", bg="blue")
        self.scan_btn.config(text="Start Scanning", bg="purple")
        self.status_label.config(text="Status: Stopped", fg="blue")
        self.detection_status.config(text="Detection: Inactive", fg="orange")
        self.fps_label.config(text="FPS: --")

        if self.cap:
            self.cap.release()
            self.cap = None

        # Clear display
        self.video_label.config(image=None, text="Camera Stopped\nPress 'Start Camera'")

    def capture_frames(self):
        """Capture frames in separate thread"""
        print("Capture thread started")

        while self.running and self.cap:
            ret, frame = self.cap.read()

            if not ret:
                print("Failed to read frame")
                self.window.after(0, self.on_camera_error)
                break

            # If detection is enabled, run YOLO
            if self.detecting and self.model is not None:
                detection_frame = frame.copy()
                self.run_detection(detection_frame)

            # Put frame in queue
            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                try:
                    self.frame_queue.get_nowait()
                    self.frame_queue.put_nowait(frame)
                except:
                    pass

            time.sleep(0.01)

        print("Capture thread ended")

    def run_detection(self, frame):
        """Run YOLO detection on frame"""
        try:
            results_list = self.model(frame, verbose=False)
            if results_list:
                results = results_list[0]
                detections = []

                if hasattr(results, "boxes"):
                    for box in results.boxes:
                        x1, y1, x2, y2 = box.xyxy[0]
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])

                        if conf >= self.CONF_THRES:
                            label = self.CUSTOM_NAMES.get(cls_id, f"class_{cls_id}")
                            x1_i, y1_i, x2_i, y2_i = map(int, [x1, y1, x2, y2])

                            detections.append({
                                'label': label,
                                'confidence': conf,
                                'bbox': (x1_i, y1_i, x2_i, y2_i),
                                'center': ((x1_i + x2_i) // 2, (y1_i + y2_i) // 2)
                            })

                # Update results in main thread
                if detections:
                    self.window.after(0, self.update_detection_results, detections)

                # Put annotated frame in queue
                annotated_frame = self.draw_detections(frame, detections)
                try:
                    self.detection_queue.put_nowait(annotated_frame)
                except queue.Full:
                    try:
                        self.detection_queue.get_nowait()
                        self.detection_queue.put_nowait(annotated_frame)
                    except:
                        pass

        except Exception as e:
            print(f"Detection error: {e}")

    def draw_detections(self, frame, detections):
        """Draw detection boxes on frame"""
        annotated = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            label = det['label']
            conf = det['confidence']

            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw label
            text = f"{label} {conf:.2f}"
            (text_width, text_height), baseline = cv2.getTextSize(
                text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
            )

            # Draw background for text
            cv2.rectangle(annotated,
                          (x1, y1 - text_height - 5),
                          (x1 + text_width, y1),
                          (0, 255, 0),
                          -1)

            # Draw text
            cv2.putText(annotated, text,
                        (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0, 0, 0), 2)

        return annotated

    def update_detection_results(self, detections):
        """Update detection results in GUI"""
        timestamp = time.strftime("%H:%M:%S")

        for det in detections:
            result_text = f"[{timestamp}] Found: {det['label']} (Conf: {det['confidence']:.2f})\n"
            self.results_text.insert("end", result_text)
            self.results_text.see("end")

            # Store for later analysis
            self.detected_items.append({
                'time': timestamp,
                'item': det['label'],
                'confidence': det['confidence']
            })

    def toggle_detection(self):
        """Toggle detection on/off"""
        if not self.detecting:
            self.detecting = True
            self.detect_btn.config(text="Stop Detection", bg="red")
            self.detection_status.config(text="Detection: Active", fg="green")
            self.status_label.config(text="Status: Detecting objects...", fg="orange")
        else:
            self.detecting = False
            self.detect_btn.config(text="Start Detection", bg="blue")
            self.detection_status.config(text="Detection: Inactive", fg="orange")
            self.status_label.config(text="Status: Camera Running", fg="green")

    def start_scanning(self):
        """Start automated scanning of surroundings"""
        if not self.scanning:
            self.scanning = True
            self.scan_btn.config(text="Stop Scanning", bg="red")
            self.status_label.config(text="Status: Scanning surroundings...", fg="purple")
            self.current_scan_index = 0

            # Start scanning thread
            self.scan_thread = threading.Thread(target=self.scan_surroundings, daemon=True)
            self.scan_thread.start()
        else:
            self.scanning = False
            self.scan_btn.config(text="Start Scanning", bg="purple")
            self.status_label.config(text="Status: Camera Running", fg="green")

    def scan_surroundings(self):
        """Automated scanning routine"""
        while self.scanning and self.running:
            # Move to next scanning position
            if self.current_scan_index < len(self.scan_positions):
                position = self.scan_positions[self.current_scan_index]
                self.move_to_position(position)

                # Wait for movement to complete
                time.sleep(2)

                # Enable detection for this position
                self.window.after(0, lambda: self.detection_status.config(
                    text=f"Detection: Scanning position {self.current_scan_index + 1}", fg="green"))

                # Wait for detection
                time.sleep(3)

                self.current_scan_index += 1
            else:
                # Return to center and start over
                self.current_scan_index = 0
                self.move_to_position(self.scan_positions[0])
                time.sleep(2)

    def move_to_position(self, angles):
        """Move DOFBOT to specific position"""
        if DOFBOT_AVAILABLE:
            # Move all 6 servos
            self.arm.Arm_serial_servo_write6(*angles, 1000)
        else:
            print(f"Moving to position: {angles}")

    def move_arm(self, pan_delta, tilt_delta):
        """Move arm manually (relative movement)"""
        if DOFBOT_AVAILABLE:
            # Example: move servo 1 (pan) and servo 2 (tilt)
            # You'll need to track current positions for proper implementation
            print(f"Moving arm: pan={pan_delta}, tilt={tilt_delta}")
            # Implement based on your DOFBOT's servo configuration
        else:
            print(f"Simulated move: pan={pan_delta}, tilt={tilt_delta}")

    def center_arm(self):
        """Center the arm"""
        self.move_to_position(self.scan_positions[0])

    def update_gui(self):
        """Update GUI with latest frame"""
        if not self.running:
            return

        try:
            # Get frame from appropriate queue
            if self.detecting and not self.detection_queue.empty():
                frame = self.detection_queue.get_nowait()
            elif not self.frame_queue.empty():
                frame = self.frame_queue.get_nowait()
            else:
                # No frame available
                self.window.after(33, self.update_gui)
                return

            # Calculate FPS
            current_time = time.time()
            self.frame_count += 1

            if current_time - self.last_time >= 1.0:
                fps = self.frame_count / (current_time - self.last_time)
                self.fps_label.config(text=f"FPS: {fps:.1f}")
                self.frame_count = 0
                self.last_time = current_time

            # Resize frame to fit label
            label_width = self.video_label.winfo_width()
            label_height = self.video_label.winfo_height()

            if label_width > 10 and label_height > 10:
                # Get frame dimensions
                height, width = frame.shape[:2]

                # Calculate aspect ratio
                frame_aspect = width / height
                label_aspect = label_width / label_height

                if label_aspect > frame_aspect:
                    # Fit to height
                    display_height = label_height
                    display_width = int(display_height * frame_aspect)
                else:
                    # Fit to width
                    display_width = label_width
                    display_height = int(display_width / frame_aspect)

                # Resize frame
                if display_width > 0 and display_height > 0:
                    frame = cv2.resize(frame, (display_width, display_height))

            # Convert to PhotoImage
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
            imgtk = ImageTk.PhotoImage(image=img_pil)

            # Update label
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)

        except queue.Empty:
            pass
        except Exception as e:
            print(f"GUI update error: {e}")

        # Schedule next update
        self.window.after(33, self.update_gui)

    def on_camera_error(self):
        """Handle camera errors"""
        self.stop_camera()
        self.status_label.config(text="Status: Camera Error", fg="red")
        self.video_label.config(text="Camera Error\nPlease check DOFBOT connection")

    def clear_results(self):
        """Clear detection results"""
        self.results_text.delete(1.0, "end")
        self.detected_items = []

    def on_closing(self):
        """Cleanup on window close"""
        self.stop_camera()
        self.scanning = False
        self.window.destroy()


def main():
    """Main function"""
    root = tk.Tk()
    app = DOFBOTCameraGUI(root)

    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

    root.mainloop()


if __name__ == "__main__":
    main()