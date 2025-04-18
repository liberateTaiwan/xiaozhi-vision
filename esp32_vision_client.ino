#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <base64.h>
#include "esp_camera.h"
#include "driver/i2s.h"
#include <WebSocketsClient.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Server settings
const char* serverUrl = "ws://10.255.0.180:8111/xiaozhi/v1/";
const char* deviceId = "ESP32-CAM-001";  // 设备唯一标识
const char* authToken = "your-token1";    // 认证token

// Camera pins for ESP32-CAM
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Audio recording settings
#define I2S_WS_PIN      15
#define I2S_SCK_PIN     14
#define I2S_SD_PIN      12
#define I2S_PORT        I2S_NUM_0
#define SAMPLE_RATE     16000
#define SAMPLE_BITS     16
#define BUFFER_SIZE     1024
#define RECORD_TIME     3  // seconds

// Function prototypes
void initWiFi();
void initCamera();
void initMicrophone();
String captureImage();
String recordAudio();
void processResponse(String response);
void playAudio(const char* audioUrl);
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length);
void sendHelloMessage();
void handleWebSocketMessage(uint8_t * payload, size_t length);
void handleListenCommand(JsonDocument& doc);

void setup() {
  Serial.begin(115200);
  
  // Initialize components
  initWiFi();
  initCamera();
  initMicrophone();
  
  Serial.println("ESP32 vision client ready");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection lost. Reconnecting...");
    initWiFi();
  }
  
  // Create WebSocket connection
  WebSocketsClient webSocket;
  webSocket.begin(serverUrl);
  webSocket.setReconnectInterval(5000);
  
  // Add authentication headers
  webSocket.setExtraHeaders("device-id: ESP32-CAM-001\r\nAuthorization: Bearer your-token1");
  
  webSocket.onEvent(webSocketEvent);
  
  while (webSocket.connected()) {
    webSocket.loop();
    
    // Wait for button press or other trigger
    // For this example, we'll just wait 10 seconds between captures
    delay(10000);
    
    Serial.println("Capturing image...");
    String imageBase64 = captureImage();
    if (imageBase64.length() == 0) {
      Serial.println("Failed to capture image");
      return;
    }
    
    Serial.println("Recording audio...");
    String audioBase64 = recordAudio();
    
    // Create JSON payload
    DynamicJsonDocument doc(imageBase64.length() + audioBase64.length() + 200);
    doc["image"] = imageBase64;
    doc["audio"] = audioBase64;
    
    // We'll rely on server-side speech recognition for this example
    // In a real implementation, you might want to use ESP32's speech recognition
    
    String payload;
    serializeJson(doc, payload);
    
    // Send to server
    HTTPClient http;
    http.begin(String(serverUrl) + "?type=process");
    http.addHeader("Content-Type", "application/json");
    
    int httpResponseCode = http.POST(payload);
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println("Server response: " + response);
      
      // Process the response
      processResponse(response);
    } else {
      Serial.print("Error on sending POST: ");
      Serial.println(httpResponseCode);
    }
    
    http.end();
  }
}

void initWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("Connected to WiFi network with IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("Failed to connect to WiFi");
  }
}

void initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Initialize with high quality
  config.frame_size = FRAMESIZE_VGA; // 640x480
  config.jpeg_quality = 10;          // 0-63, lower number means higher quality
  config.fb_count = 2;

  // Initialize the camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }
  
  Serial.println("Camera initialized successfully");
}

void initMicrophone() {
  esp_err_t err;
  
  // I2S configuration for microphone
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = (i2s_bits_per_sample_t)SAMPLE_BITS,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = BUFFER_SIZE,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };
  
  // I2S pin configuration
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK_PIN,
    .ws_io_num = I2S_WS_PIN,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD_PIN
  };
  
  // Initialize I2S driver
  err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("Failed to install I2S driver: %d\n", err);
    return;
  }
  
  // Set I2S pins
  err = i2s_set_pin(I2S_PORT, &pin_config);
  if (err != ESP_OK) {
    Serial.printf("Failed to set I2S pins: %d\n", err);
    return;
  }
  
  Serial.println("Microphone initialized successfully");
}

String captureImage() {
  // Capture an image from the camera
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    return "";
  }
  
  // Convert to base64
  String base64Image = base64::encode(fb->buf, fb->len);
  
  // Release the frame buffer
  esp_camera_fb_return(fb);
  
  Serial.printf("Captured image: %d bytes, Base64: %d bytes\n", fb->len, base64Image.length());
  return base64Image;
}

String recordAudio() {
  // Record audio for RECORD_TIME seconds
  uint32_t samples = SAMPLE_RATE * RECORD_TIME;
  size_t bytesRead = 0;
  size_t bytesToRead = samples * (SAMPLE_BITS / 8);
  uint8_t *audioBuffer = (uint8_t *)malloc(bytesToRead);
  
  if (!audioBuffer) {
    Serial.println("Failed to allocate memory for audio buffer");
    return "";
  }
  
  Serial.println("Recording...");
  
  // Clear I2S buffer before recording
  i2s_zero_dma_buffer(I2S_PORT);
  
  // Start recording
  size_t bytesTotal = 0;
  while (bytesTotal < bytesToRead) {
    i2s_read(I2S_PORT, audioBuffer + bytesTotal, bytesToRead - bytesTotal, &bytesRead, portMAX_DELAY);
    bytesTotal += bytesRead;
    Serial.printf("Recorded %d/%d bytes\n", bytesTotal, bytesToRead);
  }
  
  Serial.println("Recording finished");
  
  // Convert to base64
  String base64Audio = base64::encode(audioBuffer, bytesToRead);
  
  // Free the buffer
  free(audioBuffer);
  
  return base64Audio;
}

void processResponse(String response) {
  // Parse JSON response
  DynamicJsonDocument doc(4096);
  DeserializationError error = deserializeJson(doc, response);
  
  if (error) {
    Serial.print("deserializeJson() failed: ");
    Serial.println(error.c_str());
    return;
  }
  
  // Extract text and audio URL
  String message = doc["message"].as<String>();
  String audioUrl = doc["audio_url"].as<String>();
  
  Serial.println("Message from server: " + message);
  
  // Play audio if available
  if (audioUrl.length() > 0) {
    Serial.println("Playing audio from URL: " + audioUrl);
    playAudio(audioUrl.c_str());
  }
}

void playAudio(const char* audioUrl) {
  // Request the audio file from the server
  HTTPClient http;
  http.begin(String(serverUrl) + "?type=get_audio&audio_url=" + audioUrl);
  
  int httpResponseCode = http.GET();
  if (httpResponseCode > 0) {
    // Get the audio data
    uint8_t *audioData = http.getStreamPtr()->getBuffer();
    size_t audioLen = http.getSize();
    
    Serial.printf("Received audio: %d bytes\n", audioLen);
    
    // Here you would play the audio through I2S DAC or external audio player
    // For simplicity, we'll just print a message
    Serial.println("Audio would be playing now");
    
    // In a real implementation, you would:
    // 1. Configure I2S for output
    // 2. Write the audio data to I2S
    // i2s_write(I2S_PORT, audioData, audioLen, &bytesWritten, portMAX_DELAY);
  } else {
    Serial.print("Error getting audio: ");
    Serial.println(httpResponseCode);
  }
  
  http.end();
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("WebSocket Disconnected!");
      break;
    case WStype_CONNECTED:
      Serial.println("WebSocket Connected!");
      // Send hello message after connection
      sendHelloMessage();
      break;
    case WStype_TEXT:
      Serial.printf("WebSocket Text: %s\n", payload);
      handleWebSocketMessage(payload, length);
      break;
    case WStype_ERROR:
      Serial.println("WebSocket Error!");
      break;
    case WStype_PING:
      Serial.println("WebSocket Ping!");
      break;
    case WStype_PONG:
      Serial.println("WebSocket Pong!");
      break;
  }
}

void sendHelloMessage() {
  StaticJsonDocument<200> doc;
  doc["type"] = "hello";
  doc["device_id"] = deviceId;
  
  String message;
  serializeJson(doc, message);
  webSocket.sendTXT(message);
}

void handleWebSocketMessage(uint8_t * payload, size_t length) {
  // Convert payload to string
  char message[length + 1];
  memcpy(message, payload, length);
  message[length] = '\0';
  
  // Parse JSON message
  StaticJsonDocument<1024> doc;
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.println("Failed to parse JSON message");
    return;
  }
  
  // Handle different message types
  const char* type = doc["type"];
  if (strcmp(type, "listen") == 0) {
    // Handle listen command
    handleListenCommand(doc);
  }
  // Add more message type handlers as needed
}

void handleListenCommand(JsonDocument& doc) {
  const char* state = doc["state"];
  if (strcmp(state, "start") == 0) {
    // Start recording audio
    startRecording();
  } else if (strcmp(state, "stop") == 0) {
    // Stop recording and send audio
    stopRecordingAndSend();
  }
} 