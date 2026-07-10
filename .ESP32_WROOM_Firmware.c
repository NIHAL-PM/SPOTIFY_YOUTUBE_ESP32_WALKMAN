#include <Arduino.h>
#include <WiFi.h>
#include <U8g2lib.h>
#include <Wire.h>
#include "Audio.h"
#include "BluetoothA2DPSource.h"
#include <HTTPClient.h>
#include <ArduinoJson.h>

U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);
BluetoothA2DPSource a2dp_source;
Audio audio;

// Configuration
const int TOUCH_PIN = 13;
int dynamicTouchThreshold = 0; 

// If testing locally inside a Bridged VM, swap this URL to your VM's IP address:
// e.g., "http://192.168.1.75:5000/control/next"
const char* renderEndpoint = "https://your-app.onrender.com/control/next";

// FreeRTOS Task Handles
TaskHandle_t AudioTaskHandle;
TaskHandle_t UITaskHandle;

int32_t get_sound_data(uint8_t *data, int32_t len) { return len; }

// --- CORE 0 TASK: Main Audio Stream Engine ---
void AudioLoopTask(void * pvParameters) {
  for(;;) {
    audio.loop(); 
    vTaskDelay(pdMS_TO_TICKS(1)); // Feeds the watchdog timer
  }
}

// Fetch track details from server and pipe directly into the decoder
void fetchNextTrack() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(renderEndpoint);
    int httpCode = http.GET();
    
    if (httpCode == 200) {
      String payload = http.getString();
      JsonDocument doc;
      deserializeJson(doc, payload);
      
      const char* track = doc["track"];
      const char* artist = doc["artist"];
      const char* stream_url = doc["stream_url"];
      
      // Update 1.3" OLED UI screen
      u8g2.clearBuffer();
      u8g2.drawStr(0, 20, track);
      u8g2.drawStr(0, 40, artist);
      u8g2.sendBuffer();
      
      // Feed streaming URL right into Wi-Fi decoder
      audio.connecttohost(stream_url);
    }
    http.end();
  }
}

// --- CORE 1 TASK: Touch Processing & UI Rendering ---
void UILoopTask(void * pvParameters) {
  unsigned long lastTouchTime = 0;
  
  for(;;) {
    int touchValue = touchRead(TOUCH_PIN);
    
    // Evaluate touch baseline using the calibrated boot values
    if (touchValue < dynamicTouchThreshold && touchValue > 0) {
      if (millis() - lastTouchTime > 1500) { // 1.5s skip debounce window
        u8g2.clearBuffer();
        u8g2.drawStr(0, 30, "Fetching next...");
        u8g2.sendBuffer();
        
        fetchNextTrack();
        lastTouchTime = millis();
      }
    }
    vTaskDelay(pdMS_TO_TICKS(50)); // Poll touch wire 20 times per second
  }
}

void setup() {
  Wire.begin(21, 22);
  u8g2.begin();
  u8g2.setFont(u8g2_font_6x10_tr);
  
  // 1. Adaptive Touch Calibration Loop
  u8g2.drawStr(0, 20, "Calibrating Touch...");
  u8g2.sendBuffer();
  long sampleSum = 0;
  for(int i=0; i<20; i++) {
    sampleSum += touchRead(TOUCH_PIN);
    delay(50);
  }
  // Set threshold to 70% of the room's current electrical baseline
  dynamicTouchThreshold = (sampleSum / 20) * 0.7; 

  // 2. Wi-Fi Boot Configuration
  u8g2.clearBuffer();
  u8g2.drawStr(0, 20, "Connecting Wi-Fi...");
  u8g2.sendBuffer();
  
  WiFi.begin("YOUR_WIFI_SSID", "YOUR_WIFI_PASSWORD");
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  
  // CRUCIAL: Disable Wi-Fi modem sleep cycles to prevent Bluetooth coexistence drops
  WiFi.setSleep(false); 
  
  // Allocate a large coexistence ring buffer for the incoming audio chunks
  audio.setBufsize(35000); 
  a2dp_source.start(get_sound_data);

  // 3. FreeRTOS Core Allocation
  xTaskCreatePinnedToCore(
    AudioLoopTask,     /* Task function */
    "AudioTask",       /* Name */
    10000,             /* Stack size */
    NULL,              /* Parameters */
    3,                 /* Execution Priority */
    &AudioTaskHandle,  /* Handle */
    0                  /* Pin strictly to Core 0 (Radio Management) */
  );

  xTaskCreatePinnedToCore(
    UILoopTask,
    "UITask",
    5000,
    NULL,
    1,                 /* Execution Priority */
    &UITaskHandle,
    1                  /* Pin strictly to Core 1 (Application UI) */
  );
  
  fetchNextTrack(); // Boot up with the first algorithmic song choice
}

void loop() {
  // Empty. FreeRTOS handles loop routines concurrently on Core 0 and Core 1.
}