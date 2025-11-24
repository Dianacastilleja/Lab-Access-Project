import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from datetime import datetime
import cv2
from PIL import Image, ImageTk
import sqlite3

ADMIN_PASSCODE = "1234"          # TODO: change for real use
CAMERA_INDEX = 0                

class AccessApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Face Recognition Access Control")
        self.configure(bg="#101018")
        self.geometry("420x720")  # phone-like aspect ratio

        # current lab metadata (could later be dynamic)
        self.current_building = "EIEAB"
        self.current_room = "2.126"

        # visit log: (building, room, name) -> count
        self.visit_counts = {}

        # UI elements that will be set on the scan screen
        self.camera_frame = None
        self.preview_frame = None
        self.status_label = None
        self.time_label = None
        self.lab_label = None

        # OpenCV / camera state
        self.cap = None              # cv2.VideoCapture
        self.current_frame = None    # last captured frame
        self.camera_photo = None     # Tk image for main camera view
        self.preview_photo = None    # Tk image for preview box

        # release camera on close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.show_home()

    # ---------- generic helpers ----------

    def clear_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

    def show_home(self):
        self.clear_screen()

        container = tk.Frame(self, bg="#101018")
        container.pack(expand=True, fill="both", padx=20, pady=40)

        title = tk.Label(
            container,
            text="Face Recognition\nAccess Control System",
            font=("Helvetica", 18, "bold"),
            fg="white",
            bg="#101018",
            justify="center",
        )
        title.pack(pady=(0, 40))

        ttk.Button(
            container,
            text="Scan to Enter Lab",
            command=self.show_scan_screen,
            width=25,
        ).pack(pady=10, ipady=5)

        ttk.Button(
            container,
            text="Register",
            command=self.show_admin_login,
            width=25,
        ).pack(pady=10, ipady=5)
    
    # ---------- database functions ----------

    def set_tables(self):
        conn = sqlite3.connect("thedatabase.db")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS Lab (lab_id INTEGER PRIMARY KEY, lab_name TEXT, facial_id TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS LabMember (member_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, facial_id BLOB, lab_id TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS LabAccess (accessID INTEGER PRIMARY KEY, member_id INTEGER, lab_id INTEGER, time_stamp TEXT, access_type TEXT, result TEXT, FOREIGN KEY(member_id) REFERENCES LabMember(member_id), FOREIGN KEY(lab_id) REFERENCES Lab(lab_id))")
        conn.commit()
        conn.close()

    def connect_db(self, db_name):
        conn = sqlite3.connect(db_name)
        return conn
    
    def fetch_data(self, conn, table_name):
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        data = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        return data, column_names
    
    def edit_record_view(self,event):
        tree=event.widget
        selected = tree.selection()

        if not selected:
            return
        
        values = tree.item(selected[0], "values")
        self.current_edit_item = selected[0]
        self.current_edit_values = values

        win = tk.Toplevel(self)
        win.title("Edit Record")
        win.geometry("350x400")
        win.configure(bg="#101018")

        tk.Label(win, text="Edit Record", fg="white", bg="#101018", font=("Helvetica", 14)).pack(pady=10)

        self.edit_entries = []
        self.edit_column_names = self.last_column_names

        print(self.edit_column_names)

        for col, val in zip(self.edit_column_names, values):
            tk.Label(win, text=col, fg="white", bg="#101018").pack(pady=5)
            entry = tk.Entry(win)
            entry.insert(0,val)

            print(self.primary_key_column)

            if col == self.primary_key_column:
                entry.config(state="readonly")
            
            entry.pack(pady=5)
            self.edit_entries.append(entry)
        
        tk.Button(win, text="Save", command=lambda: self.save_record_changes(win)).pack(pady=20)

    def save_record_changes(self,window):
        conn = self.connect_db("thedatabase.db")
        cursor = conn.cursor()

        new_values = [entry.get() for entry in self.edit_entries]

        primary_key_col = self.primary_key_column
        pk_idx = self.edit_column_names.index(primary_key_col)
        primary_key_value = self.current_edit_values[pk_idx]

        editable_columns = [col for col in self.edit_column_names if col != primary_key_col]
        set_clause = ", ".join([f"{col} = ?" for col in editable_columns])

        print(self.last_table_name)
        print(set_clause)
        print(primary_key_col)
        sql = f"UPDATE {self.last_table_name} SET {set_clause} WHERE {primary_key_col} = ?"

        print("SQL:",sql)
        editable_values =[
            new_values[self.edit_column_names.index(col)]
            for col in editable_columns
        ]
        cursor.execute(sql, editable_values + [primary_key_value])
        conn.commit()
        conn.close()

        window.destroy()
        self.show_admin_panel()
    
    def display_data_in_treeview(self,root, data, column_names):
        tree = ttk.Treeview(root, columns=column_names, show='headings')

        for col in column_names:
            tree.heading(col, text=col.replace('_', ' ').title())
            tree.column(col, width=100, anchor='center')
        
        for row in data:
            tree.insert("","end", values=row)
        
        tree.pack(pady=10)

        tree.bind("<Double-1>", self.edit_record_view)
        return tree

    # ---------- admin / teacher flow ----------

    def show_admin_login(self):
        code = simpledialog.askstring(
            "Teacher Login", "Enter teacher passcode:", show="*"
        )
        if code is None:
            return
        if code == ADMIN_PASSCODE:
            self.show_admin_panel()
        else:
            messagebox.showerror("Access Denied", "Incorrect passcode.")

    def show_admin_panel(self):
        self.clear_screen()

        frame = tk.Frame(self, bg="#101018")
        frame.pack(expand=True, fill="both", padx=20, pady=20)

        tk.Label(
            frame,
            text="Teacher Panel\n(Future: view/edit lab database)",
            font=("Helvetica", 14, "bold"),
            fg="white",
            bg="#101018",
            justify="center",
        ).pack(pady=40)

        conn = self.connect_db("thedatabase.db")
        self.set_tables()
        data, column_names = self.fetch_data(conn, "LabMember")

        conn.close()
        self.primary_key_column = "member_id"
        self.last_column_names = column_names
        self.last_table_name = "LabMember"
    
        tree_container = tk.Frame(frame, bg="#101018")
        tree_container.pack(pady=10)
        self.display_data_in_treeview(tree_container, data, column_names)

        button_row = tk.Frame(frame,bg="#101018")
        button_row.pack(pady= 20)
        ttk.Button(button_row, text="Add New User").pack(side="left",pady=20)
        ttk.Button(button_row, text="Check Access Logs", command=self.show_access_log).pack(side="left",pady=20)

        ttk.Button(frame, text="Back", command=self.show_home).pack(pady=30)

        tk.Label(
            frame,
            text=(
                "For 4, this screen can simply state that\n"
                "only authorized teachers may register new faces.\n\n"
                "Later, you can add controls here to:\n"
                "• Capture and store new faces and in what labs they have access to\n"
                "• Remove faces\n"
                "• Review access logs"
            ),
            font=("Helvetica", 10),
            fg="#b0b0c0",
            bg="#101018",
            justify="left",
        ).pack()
    
    # ---------- access logs ----------

    def show_access_log(self):
        self.clear_screen()

        frame = tk.Frame(self, bg="#101018")
        frame.pack(expand=True, fill="both", padx=20, pady=20)

        tk.Label(
            frame,
            text="Access Logs",
            font=("Helvetica", 14, "bold"),
            fg="white",
            bg="#101018",
            justify="center",
        ).pack(pady=40)

        conn = self.connect_db("thedatabase.db")
        data, column_names = self.fetch_data(conn, "LabAccess")

        conn.close()
        self.primary_key_column = "accessID"
        self.last_column_names = column_names
        self.last_table_name = "LabAccess"
    
        tree_container = tk.Frame(frame, bg="#101018")
        tree_container.pack(pady=10)
        self.display_data_in_treeview(tree_container, data, column_names)

        button_row = tk.Frame(frame,bg="#101018")
        button_row.pack(pady= 20)

        ttk.Button(frame, text="Back", command=self.show_admin_panel).pack(pady=30)
        ttk.Button(frame, text="Home", command=self.show_home).pack(pady=30)

    # ---------- scan / access flow ----------

    def open_camera(self) -> bool:
        """Try to open a webcam by scanning indices 0–4."""
        # If already open, keep using it
        if self.cap is not None and self.cap.isOpened():
            return True

        # Close any stale handle
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        for idx in range(0, 5):
            print(f"[INFO] Trying camera index {idx}...")
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)  # DirectShow backend (Windows)

            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    print(f"[INFO] Opened camera at index {idx}.")
                    self.cap = cap
                    return True
                else:
                    print(f"[WARN] Camera index {idx} opened but frame read failed.")
                    cap.release()
            else:
                print(f"[WARN] Could not open camera at index {idx}.")

        # If we reach here, no index worked
        self.cap = None
        return False


    def show_scan_screen(self):
        self.clear_screen()

        # open camera when entering scan screen
        if not self.open_camera():
            messagebox.showerror(
                "Camera Error",
                f"Could not open camera at index {CAMERA_INDEX}. "
                "Check camera permissions or change CAMERA_INDEX.",
            )
            self.show_home()
            return

        # top bar
        top = tk.Frame(self, bg="#1a1a26")
        top.pack(fill="x")

        tk.Label(
            top,
            text="Face recognition access control system",
            font=("Helvetica", 11, "bold"),
            fg="#e0e0ff",
            bg="#1a1a26",
        ).pack(side="left", padx=10, pady=8)

        tk.Label(
            top,
            text="Temperature: --.-  Normal",
            font=("Helvetica", 10),
            fg="#a0ffa0",
            bg="#1a1a26",
        ).pack(side="right", padx=10)

        # camera area
        center = tk.Frame(self, bg="#101018")
        center.pack(expand=True, fill="both", pady=(10, 0))

        camera_container = tk.Frame(
            center,
            bg="#000000",
            highlightthickness=2,
            highlightbackground="#444444",
        )
        camera_container.pack(padx=30, pady=10, fill="both", expand=True)

        self.camera_frame = tk.Label(
            camera_container,
            fg="#aaaaaa",
            bg="#000000",
            font=("Helvetica", 12),
            justify="center",
        )
        self.camera_frame.pack(expand=True, fill="both")

        # bottom panel
        bottom = tk.Frame(self, bg="#101018")
        bottom.pack(fill="x", pady=(5, 15))

        # line 1: lab and time
        info_row = tk.Frame(bottom, bg="#101018")
        info_row.pack(fill="x", padx=20, pady=(0, 5))

        self.lab_label = tk.Label(
            info_row,
            text=f"{self.current_building} – Lab {self.current_room}",
            font=("Helvetica", 11, "bold"),
            fg="#e0e0ff",
            bg="#101018",
        )
        self.lab_label.pack(side="left")

        self.time_label = tk.Label(
            info_row,
            text="--:--",
            font=("Helvetica", 11),
            fg="#e0e0ff",
            bg="#101018",
        )
        self.time_label.pack(side="right")

        # line 2: preview + status
        preview_row = tk.Frame(bottom, bg="#101018")
        preview_row.pack(fill="x", padx=20, pady=(5, 10))

        preview_container = tk.Frame(
            preview_row,
            bg="#000000",
            width=80,
            height=80,
            highlightthickness=2,
            highlightbackground="#444444",
        )
        preview_container.pack(side="left")
        preview_container.pack_propagate(False)

        self.preview_frame = tk.Label(
            preview_container,
            fg="#aaaaaa",
            bg="#000000",
            font=("Helvetica", 9),
        )
        self.preview_frame.pack(expand=True, fill="both")

        self.status_label = tk.Label(
            preview_row,
            text="Please look at the camera…",
            font=("Helvetica", 11),
            fg="#e0e0ff",
            bg="#101018",
            justify="left",
        )
        self.status_label.pack(side="left", padx=15)

        # line 3: buttons
        btn_row = tk.Frame(bottom, bg="#101018")
        btn_row.pack(fill="x", padx=20, pady=(5, 0))

        ttk.Button(
            btn_row,
            text="Simulate Scan",
            command=self.simulate_scan_result,
        ).pack(side="left")

        ttk.Button(btn_row, text="Back", command=self.back_from_scan).pack(side="right")

        # start updating time and camera
        self.update_time()
        self.update_camera()

    def back_from_scan(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            print("[INFO] Camera released from back button.")
        self.cap = None
        self.show_home()

    # ---------- time and camera updates ----------

    def update_time(self):
        now = datetime.now()
        time_str = now.strftime("%H:%M  %B %d, %A")
        if self.time_label is not None:
            try:
                self.time_label.config(text=time_str)
            except tk.TclError:
                pass
        self.after(1000, self.update_time)

    def update_camera(self):
        """Grab a frame from OpenCV and display it in the Tkinter widgets."""
        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                print("[WARN] Failed to grab frame from camera.")
            else:
                self.current_frame = frame

                # mirror horizontally and convert BGR -> RGB
                frame_rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)

                # big image for main camera view
                big_img = Image.fromarray(frame_rgb).resize((320, 400))
                self.camera_photo = ImageTk.PhotoImage(big_img)
                try:
                    self.camera_frame.config(image=self.camera_photo, text="")
                except tk.TclError:
                    pass

                # small image for preview box
                small_img = big_img.resize((80, 80))
                self.preview_photo = ImageTk.PhotoImage(small_img)
                try:
                    self.preview_frame.config(image=self.preview_photo, text="")
                except tk.TclError:
                    pass

        self.after(30, self.update_camera)

    # ---------- recognition integration ----------

    def simulate_scan_result(self):
        """
        For now:
        - Ensure we have a frame from the camera.
        - Optionally save it as an image (for debugging / Aiden).
        - Ask for the recognized name, then show welcome message.
        """
        if self.current_frame is None:
            messagebox.showwarning(
                "No frame",
                "No camera frame available yet. Please wait a moment and try again.",
            )
            return

        # Optional: save the frame so Aiden can inspect it or test his model.
        # This writes a BGR image as captured by OpenCV.
        cv2.imwrite("last_scan_frame.jpg", self.current_frame)

        name = simpledialog.askstring(
            "Simulated Scan",
            "Recognized person’s name (for now, type it):",
        )
        if not name:
            return

        self.handle_recognition_result(name.strip())


    def handle_recognition_result(self, name: str):
        """
        Called whenever a face has been recognized for the current lab.
        Determines whether this is a first visit or a returning visit,
        updates the welcome message, and lights borders green.
        """
        key = (self.current_building, self.current_room, name)
        previous_visits = self.visit_counts.get(key, 0)
        self.visit_counts[key] = previous_visits + 1

        first_time = previous_visits == 0

        # border turns green
        for widget in (self.camera_frame, self.preview_frame):
            if widget is not None:
                parent = widget.master
                try:
                    parent.configure(
                        highlightthickness=3,
                        highlightbackground="#00ff00",
                    )
                except tk.TclError:
                    pass

        msg = (
            f"Welcome To the Lab {name} !"
            if first_time
            else f"Welcome Back {name} !"
        )

        if self.status_label is not None:
            try:
                self.status_label.config(text=msg, fg="#00ff00")
            except tk.TclError:
                pass

    # ---------- clean shutdown ----------

    def on_close(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            print("[INFO] Camera released on window close.")
        self.destroy()


if __name__ == "__main__":
    app = AccessApp()
    app.mainloop()
