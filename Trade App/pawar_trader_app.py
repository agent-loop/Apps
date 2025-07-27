# file: pawar_trader_app.py
import customtkinter as ctk
import threading
import time
import requests
import os
from PIL import Image
from datetime import datetime, time as dt_time, timedelta

# Import our own modules
import trading_logic
import database

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Basic App Setup ---
        self.title("PAWAR TRADING")
        self.geometry("700x550")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        
        # --- App State Variables ---
        self.client_id = None
        self.access_token = None
        self.scheduled_job = None
        self.execution_thread = None
        self.is_running = False

        # --- Load Assets ---
        bg_image_path = os.path.join("assets", "background.png")
        logo_image_path = os.path.join("assets", "logo.png")
        self.bg_image = ctk.CTkImage(Image.open(bg_image_path), size=(700, 550))
        self.logo_image = ctk.CTkImage(Image.open(logo_image_path), size=(128, 128))

        # --- Background Label ---
        self.bg_label = ctk.CTkLabel(self, text="", image=self.bg_image)
        self.bg_label.place(relwidth=1, relheight=1)

        # --- Initialize UI Components (will be placed later) ---
        self.splash_frame = None
        self.main_frame = None
        self.countdown_frame = None
        self.log_frame = None
        
        # --- Start Application Flow ---
        self.after(100, self.check_internet_and_show_splash)
        
    def check_internet_and_show_splash(self):
        try:
            requests.get("http://www.google.com", timeout=5)
            self.show_splash_screen()
        except (requests.ConnectionError, requests.Timeout):
            ctk.CTkLabel(self, text="No Internet Connection.\nPlease connect and restart the app.", font=("Arial", 18, "bold")).pack(pady=200)
    
    def show_splash_screen(self):
        self.splash_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.splash_frame.pack(expand=True, fill="both")
        ctk.CTkLabel(self.splash_frame, text="", image=self.logo_image).pack(pady=(150, 20))
        self.after(4000, self.setup_credentials_or_main_ui)

    def setup_credentials_or_main_ui(self):
        if self.splash_frame:
            self.splash_frame.destroy()

        database.init_db()
        creds = database.get_credentials()
        if not creds:
            self.show_credentials_dialog()
        else:
            self.client_id, self.access_token = creds
            self.setup_main_ui()

    def show_credentials_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Enter Credentials")
        dialog.geometry("400x250")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="DhanHQ Credentials", font=("Arial", 16, "bold")).pack(pady=10)
        
        ctk.CTkLabel(dialog, text="Client ID:").pack(padx=20, pady=(10, 0), anchor="w")
        client_id_entry = ctk.CTkEntry(dialog, width=360)
        client_id_entry.pack(padx=20, pady=5)
        
        ctk.CTkLabel(dialog, text="Access Token:").pack(padx=20, pady=(10, 0), anchor="w")
        access_token_entry = ctk.CTkEntry(dialog, width=360, show="*")
        access_token_entry.pack(padx=20, pady=5)
        
        def save_and_continue():
            client_id = client_id_entry.get()
            access_token = access_token_entry.get()
            if client_id and access_token:
                database.save_credentials(client_id, access_token)
                self.client_id, self.access_token = client_id, access_token
                dialog.destroy()
                self.setup_main_ui()

        ctk.CTkButton(dialog, text="Save and Continue", command=save_and_continue).pack(pady=20)
        
    def setup_main_ui(self):
        if hasattr(self, 'main_frame') and self.main_frame:
            self.main_frame.destroy()
            
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(expand=True, fill="both")

        ctk.CTkLabel(self.main_frame, text="PAWAR TRADING", font=("Impact", 48, "bold")).pack(pady=(20, 25))

        # Input fields
        inputs = [
            ("Chartink Screener Link:", "link_entry", "https://chartink.com/screener/copy-001-49?src=wassup"),
            ("Total Amount (₹):", "amount_entry", "1000.00"),
            ("Profit Percent (%):", "profit_entry", "1.50"),
            ("Loss Percent (%):", "loss_entry", "1.00"),
            ("Number of Stocks to Buy:", "stocks_entry", "2")
        ]
        
        for label, attr, default in inputs:
            frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
            frame.pack(pady=4, padx=50, fill="x")
            ctk.CTkLabel(frame, text=label, width=200, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=300)
            entry.pack(side="right")
            entry.insert(0, default)
            setattr(self, attr, entry)
        
        # Time input
        time_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        time_frame.pack(pady=15)
        ctk.CTkLabel(time_frame, text="Execution Time:").pack(side="left", padx=5)
        self.hour_entry = ctk.CTkEntry(time_frame, width=40)
        self.hour_entry.pack(side="left")
        ctk.CTkLabel(time_frame, text=":").pack(side="left")
        self.min_entry = ctk.CTkEntry(time_frame, width=40)
        self.min_entry.pack(side="left")
        ctk.CTkLabel(time_frame, text=":").pack(side="left")
        self.sec_entry = ctk.CTkEntry(time_frame, width=40)
        self.sec_entry.pack(side="left")
        self.ampm_var = ctk.StringVar(value="AM")
        ctk.CTkOptionMenu(time_frame, variable=self.ampm_var, values=["AM", "PM"]).pack(side="left", padx=5)

        # Submit button
        ctk.CTkButton(self.main_frame, text="Schedule Execution", command=self.schedule_execution, height=40, font=("Arial", 16)).pack(pady=20)

    def schedule_execution(self):
        try:
            hour = int(self.hour_entry.get())
            minute = int(self.min_entry.get())
            second = int(self.sec_entry.get())
            ampm = self.ampm_var.get()
            if ampm == "PM" and hour != 12:
                hour += 12
            if ampm == "AM" and hour == 12:
                hour = 0
            
            now = datetime.now()
            target_time = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            
            if target_time < now:
                target_time += timedelta(days=1)
            
            self.time_to_wait = (target_time - now).total_seconds()
            self.main_frame.pack_forget()
            self.show_countdown()
        except ValueError:
            # Simple error handling for invalid time input
            pass

    def show_countdown(self):
        self.countdown_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.countdown_frame.pack(expand=True, fill="both")
        
        self.countdown_label = ctk.CTkLabel(self.countdown_frame, text="", font=("Courier New", 40, "bold"))
        self.countdown_label.pack(expand=True)
        
        cancel_button = ctk.CTkButton(self.countdown_frame, text="X", command=self.cancel_execution, width=30, height=30, corner_radius=15, fg_color="red", hover_color="darkred")
        cancel_button.place(relx=0.95, rely=0.05, anchor="ne")

        self.update_countdown()

    def update_countdown(self):
        if self.time_to_wait > 0:
            mins, secs = divmod(self.time_to_wait, 60)
            hours, mins = divmod(mins, 60)
            timer_str = f"{int(hours):02}:{int(mins):02}:{int(secs):02}"
            self.countdown_label.configure(text=timer_str)
            self.time_to_wait -= 1
            self.scheduled_job = self.after(1000, self.update_countdown)
        else:
            self.start_script_execution()

    def cancel_execution(self):
        if self.scheduled_job:
            self.after_cancel(self.scheduled_job)
            self.scheduled_job = None
        self.countdown_frame.destroy()
        self.main_frame.pack(expand=True, fill="both")

    def start_script_execution(self):
        self.countdown_frame.destroy()
        self.show_log_screen()
        
        self.is_running = True
        
        # Gather inputs from UI
        link = self.link_entry.get()
        total_amount = float(self.amount_entry.get())
        profit_percent = float(self.profit_entry.get())
        loss_percent = float(self.loss_entry.get())
        no_of_stocks = int(self.stocks_entry.get())
        
        # Run trading logic in a separate thread to not freeze the GUI
        self.execution_thread = threading.Thread(
            target=trading_logic.run_trading_script,
            args=(link, total_amount, profit_percent, loss_percent, no_of_stocks, self.client_id, self.access_token, self.log_to_gui)
        )
        self.execution_thread.daemon = True # Allows app to exit even if thread is running
        self.execution_thread.start()

    def show_log_screen(self):
        self.log_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.log_frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        self.log_textbox = ctk.CTkTextbox(self.log_frame, state="disabled", font=("Courier New", 12))
        self.log_textbox.pack(expand=True, fill="both")

    def log_to_gui(self, message):
        # This function is called from the trading thread, so we must use 'after' to update the GUI safely
        def update_textbox():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.see("end") # Auto-scroll to the bottom
            self.log_textbox.configure(state="disabled")
        
        self.after(0, update_textbox)

if __name__ == "__main__":
    app = App()
    app.mainloop()