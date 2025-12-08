import cv2
import tkinter as tk
from tkinter import Label, Button, Text, Scrollbar, Frame, LabelFrame
from PIL import Image, ImageTk
import threading
import queue
import time
from Arm_Lib import Arm_Device
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


class SimpleDOFBOTCamera:
    def __init__(self, window):
        self.window = window
        self.window.title("DOFBOT Camera System")

        # Set window size
        self.window.geometry("1200x800")

        # Initialize DOFBOT Arm
        self.arm = Arm_Device()

        # Setup GUI
        self.setup_gui()

        # Initialize variables
        self.cap = None
        self.running = False
        self.frame_queue = queue.Queue(maxsize=2)
        self.last_time = time.time()
        self.frame_count = 0

        # Predefined scanning positions
        self.scan_positions = [
            [90, 90, 90, 90, 90, 90],  # Center
            [60, 90, 90, 90, 90, 90],  # Left
            [120, 90, 90, 90, 90, 90],  # Right
            [90, 60, 90, 90, 90, 90],  # Up
            [90, 120, 90, 90, 90, 90],  # Down
        ]

        # Start camera automatically
        self.window.after(500, self.start_camera_auto)

    def setup_gui(self):
        """Setup the GUI layout"""
        # Main container
        main_container = Frame(self.window)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Left panel for video
        left_panel = Frame(main_container, width=800)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Video display
        self.video_label = Label(left_panel, bg="black", text="Initializing DOFBOT Camera...",
                                 font=("Arial", 14), fg="white")
        self.video_label.pack(fill="both", expand=True)

        # FPS label
        self.fps_label = Label(left_panel, text="FPS: --", fg="green",
                               font=("Arial", 10))
        self.fps_label.pack(anchor="w", pady=(5, 0))

        # Status label
        self.status_label = Label(left_panel, text="Status: Initializing...", fg="blue",
                                  font=("Arial", 10))
        self.status_label.pack(anchor="w", pady=(2, 0))

        # Right panel for controls
        right_panel = Frame(main_container, width=300)
        right_panel.pack(side="right", fill="both", padx=(10, 0))

        # Control frame
        control_frame = LabelFrame(right_panel, text="DOFBOT Controls", font=("Arial", 12, "bold"), padx=10, pady=10)
        control_frame.pack(fill="x", pady=(0, 10))

        # Camera controls
        self.start_btn = Button(control_frame, text="Start Camera", command=self.start_camera,
                                width=20, height=2, bg="green", fg="white",
                                font=("Arial", 10, "bold"))
        self.start_btn.pack(pady=5)

        self.stop_btn = Button(control_frame, text="Stop Camera", command=self.stop_camera,
                               width=20, height=2, bg="red", fg="white", state="disabled",
                               font=("Arial", 10, "bold"))
        self.stop_btn.pack(pady=5)

        # Scan button
        self.scan_btn = Button(control_frame, text="Start Scanning", command=self.start_scanning,
                               width=20, height=2, bg="purple", fg="white",
                               font=("Arial", 10, "bold"))
        self.scan_btn.pack(pady=5)

        # Movement controls
        move_frame = LabelFrame(control_frame, text="Manual Control", font=("Arial", 10))
        move_frame.pack(fill="x", pady=10)

        # Grid layout for movement buttons
        Button(move_frame, text="↑ Up", command=lambda: self.move_arm(0, 10), width=8).grid(row=0, column=1, pady=2)
        Button(move_frame, text="← Left", command=lambda: self.move_arm(-10, 0), width=8).grid(row=1, column=0, padx=2)
        Button(move_frame, text="Center", command=self.center_arm, width=8).grid(row=1, column=1, padx=2)
        Button(move_frame, text="Right →", command=lambda: self.move_arm(10, 0), width=8).grid(row=1, column=2, padx=2)
        Button(move_frame, text="↓ Down", command=lambda: self.move_arm(0, -10), width=8).grid(row=2, column=1, pady=2)

        # DOFBOT status
        status_text = "DOFBOT: Connected" if DOFBOT_AVAILABLE else "DOFBOT: Simulation Mode"
        status_color = "green" if DOFBOT_AVAILABLE else "orange"
        self.arm_status = Label(control_frame, text=status_text, fg=status_color,
                                font=("Arial", 10))
        self.arm_status.pack(pady=10)

        # Log area
        log_frame = LabelFrame(right_panel, text="System Log", font=("Arial", 12, "bold"), padx=10, pady=10)
        log_frame.pack(fill="both", expand=True)

        scrollbar = Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")

        self.log_text = Text(log_frame, height=10, yscrollcommand=scrollbar.set,
                             font=("Consolas", 9), wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)

        # Add initial log message
        self.log("System initialized")
        self.log(f"DOFBOT: {'Connected' if DOFBOT_AVAILABLE else 'Simulation Mode'}")

    def log(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")

    def start_camera_auto(self):
        """Start camera automatically"""
        self.log("Auto-starting camera...")
        self.start_camera()

    def start_camera(self):
        """Start the camera stream"""
        if not self.running:
            self.status_label.config(text="Status: Starting camera...", fg="orange")
            self.log("Starting camera...")

            # Try to open camera
            for cam_index in [0, 1, 2]:
                self.cap = cv2.VideoCapture(cam_index)
                if self.cap.isOpened():
                    self.log(f"Camera found at index {cam_index}")
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
                self.log("Camera started successfully")

                # Start camera thread
                self.camera_thread = threading.Thread(target=self.capture_frames, daemon=True)
                self.camera_thread.start()

                # Start GUI update
                self.update_gui()
            else:
                self.status_label.config(text="Status: No camera found", fg="red")
                self.video_label.config(text="No Camera Found\nPlease check DOFBOT connection")
                self.log("ERROR: No camera found")

    def stop_camera(self):
        """Stop the camera stream"""
        self.log("Stopping camera...")
        self.running = False

        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.scan_btn.config(text="Start Scanning", bg="purple")
        self.status_label.config(text="Status: Stopped", fg="blue")
        self.fps_label.config(text="FPS: --")

        if self.cap:
            self.cap.release()
            self.cap = None

        # Clear display
        self.video_label.config(image=None, text="Camera Stopped\nPress 'Start Camera'")
        self.log("Camera stopped")

    def capture_frames(self):
        """Capture frames in separate thread"""
        self.log("Capture thread started")

        while self.running and self.cap:
            ret, frame = self.cap.read()

            if not ret:
                self.log("ERROR: Failed to read frame")
                self.window.after(0, self.on_camera_error)
                break

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

        self.log("Capture thread ended")

    def start_scanning(self):
        """Start automated scanning"""
        if not hasattr(self, 'scanning') or not self.scanning:
            self.scanning = True
            self.scan_btn.config(text="Stop Scanning", bg="red")
            self.status_label.config(text="Status: Scanning...", fg="purple")
            self.log("Starting automated scan...")

            # Start scanning thread
            self.scan_thread = threading.Thread(target=self.scan_surroundings, daemon=True)
            self.scan_thread.start()
        else:
            self.scanning = False
            self.scan_btn.config(text="Start Scanning", bg="purple")
            self.status_label.config(text="Status: Camera Running", fg="green")
            self.log("Scanning stopped")

    def scan_surroundings(self):
        """Automated scanning routine"""
        positions = ["Center", "Left", "Right", "Up", "Down"]

        while self.scanning and self.running:
            for i, position in enumerate(self.scan_positions):
                if not self.scanning:
                    break

                self.log(f"Moving to {positions[i]} position")
                self.window.after(0, lambda msg=f"Moving to {positions[i]}":
                self.status_label.config(text=f"Status: {msg}", fg="purple"))

                # Move to position
                self.move_to_position(position)
                time.sleep(2)

                # Capture frame at this position
                self.log(f"Capturing at {positions[i]} position")
                self.window.after(0, lambda msg=f"Capturing at {positions[i]}":
                self.status_label.config(text=f"Status: {msg}", fg="orange"))
                time.sleep(1)

            # Return to center
            if self.scanning:
                self.log("Returning to center")
                self.move_to_position(self.scan_positions[0])
                time.sleep(2)

    def move_to_position(self, angles):
        """Move DOFBOT to specific position"""
        if DOFBOT_AVAILABLE:
            self.arm.Arm_serial_servo_write6(*angles, 1000)
        else:
            print(f"Moving to position: {angles}")

    def move_arm(self, pan_delta, tilt_delta):
        """Move arm manually"""
        self.log(f"Manual move: pan={pan_delta}, tilt={tilt_delta}")
        if DOFBOT_AVAILABLE:
            # Implement actual servo movement here
            print(f"Moving arm: pan={pan_delta}, tilt={tilt_delta}")
        else:
            print(f"Simulated move: pan={pan_delta}, tilt={tilt_delta}")

    def center_arm(self):
        """Center the arm"""
        self.log("Centering arm")
        self.move_to_position(self.scan_positions[0])

    def update_gui(self):
        """Update GUI with latest frame"""
        if not self.running:
            return

        try:
            # Get frame from queue
            frame = self.frame_queue.get_nowait()

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
                height, width = frame.shape[:2]
                frame_aspect = width / height
                label_aspect = label_width / label_height

                if label_aspect > frame_aspect:
                    display_height = label_height
                    display_width = int(display_height * frame_aspect)
                else:
                    display_width = label_width
                    display_height = int(display_width / frame_aspect)

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
        self.video_label.config(text="Camera Error\nCheck DOFBOT connection")
        self.log("ERROR: Camera connection lost")

    def on_closing(self):
        """Cleanup on window close"""
        self.stop_camera()
        if hasattr(self, 'scanning'):
            self.scanning = False
        self.window.destroy()


def main():
    """Main function"""
    root = tk.Tk()
    app = SimpleDOFBOTCamera(root)

    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # Center window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

    root.mainloop()


if __name__ == "__main__":
    main()