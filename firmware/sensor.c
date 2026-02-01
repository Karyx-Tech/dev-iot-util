/*
 * Karyx IoT Sensor Firmware
 * 
 * CLI-based sensor firmware that reads temperature and humidity
 * and reports to the Karyx IoT Panel via HTTP API
 * 
 * Compile: make
 * Usage: ./sensor_firmware --config config.ini
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include <curl/curl.h>
#include <sys/sysinfo.h>

#define VERSION "1.0.0"
#define MAX_BUFFER 2048
#define CONFIG_LINE_MAX 256

// Configuration structure
typedef struct {
    char device_id[64];
    char device_name[128];
    char panel_url[256];
    int report_interval;
    int verbose;
} Config;

// Global variables
static volatile int running = 1;
static Config config;

// Function prototypes
void signal_handler(int signum);
void load_config(const char* filename);
float read_temperature();
float read_humidity();
int register_device();
int report_metrics(float temp, float humidity);
size_t write_callback(void *contents, size_t size, size_t nmemb, void *userp);
void print_usage(const char* program);
void log_message(const char* level, const char* message);

// Signal handler for graceful shutdown
void signal_handler(int signum) {
    log_message("INFO", "Received shutdown signal");
    running = 0;
}

// Load configuration from file
void load_config(const char* filename) {
    FILE* file = fopen(filename, "r");
    if (!file) {
        fprintf(stderr, "Error: Cannot open config file: %s\n", filename);
        exit(1);
    }

    char line[CONFIG_LINE_MAX];
    while (fgets(line, sizeof(line), file)) {
        // Skip comments and empty lines
        if (line[0] == '#' || line[0] == '\n') continue;

        char key[64], value[192];
        if (sscanf(line, "%63[^=]=%191[^\n]", key, value) == 2) {
            // Trim whitespace
            char* k = key;
            char* v = value;
            while (*k == ' ') k++;
            while (*v == ' ') v++;

            if (strcmp(k, "device_id") == 0) {
                strncpy(config.device_id, v, sizeof(config.device_id) - 1);
            } else if (strcmp(k, "device_name") == 0) {
                strncpy(config.device_name, v, sizeof(config.device_name) - 1);
            } else if (strcmp(k, "panel_url") == 0) {
                strncpy(config.panel_url, v, sizeof(config.panel_url) - 1);
            } else if (strcmp(k, "report_interval") == 0) {
                config.report_interval = atoi(v);
            } else if (strcmp(k, "verbose") == 0) {
                config.verbose = atoi(v);
            }
        }
    }

    fclose(file);
}

// Simulate temperature reading (replace with actual sensor code)
float read_temperature() {
    // Simulate reading from sensor
    // In real firmware, this would read from actual sensor (e.g., DHT22, DS18B20)
    return 22.0 + ((float)rand() / RAND_MAX) * 8.0; // 22-30°C
}

// Simulate humidity reading
float read_humidity() {
    // Simulate reading from sensor
    return 40.0 + ((float)rand() / RAND_MAX) * 20.0; // 40-60%
}

// CURL write callback
size_t write_callback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    char* buffer = (char*)userp;
    strncat(buffer, contents, realsize);
    return realsize;
}

// Register device with panel
int register_device() {
    CURL *curl;
    CURLcode res;
    char url[512];
    char response[MAX_BUFFER] = {0};
    char post_data[MAX_BUFFER];

    snprintf(url, sizeof(url), "%s/devices", config.panel_url);
    snprintf(post_data, sizeof(post_data),
        "{\"name\":\"%s\",\"device_type\":\"sensor\",\"ip_address\":\"127.0.0.1\",\"metadata\":{\"firmware_version\":\"%s\"}}",
        config.device_name, VERSION);

    curl = curl_easy_init();
    if (!curl) {
        log_message("ERROR", "Failed to initialize CURL");
        return -1;
    }

    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, post_data);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);

    res = curl_easy_perform(curl);
    
    if (res != CURLE_OK) {
        log_message("ERROR", "Device registration failed");
        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);
        return -1;
    }

    log_message("INFO", "Device registered successfully");
    
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return 0;
}

// Report metrics to panel
int report_metrics(float temp, float humidity) {
    CURL *curl;
    CURLcode res;
    char url[512];
    char response[MAX_BUFFER] = {0};
    char post_data[MAX_BUFFER];
    struct sysinfo si;

    sysinfo(&si);

    snprintf(url, sizeof(url), "%s/devices/%s", config.panel_url, config.device_id);
    snprintf(post_data, sizeof(post_data),
        "{\"status\":\"online\",\"metrics\":{\"temperature\":%.2f,\"humidity\":%.2f,\"uptime\":%ld,\"memory_usage_percent\":%ld}}",
        temp, humidity, si.uptime, (100 - ((si.freeram * 100) / si.totalram)));

    curl = curl_easy_init();
    if (!curl) {
        log_message("ERROR", "Failed to initialize CURL");
        return -1;
    }

    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, "PUT");
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, post_data);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);

    res = curl_easy_perform(curl);
    
    if (res != CURLE_OK) {
        log_message("WARN", "Failed to report metrics");
        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);
        return -1;
    }

    if (config.verbose) {
        char msg[256];
        snprintf(msg, sizeof(msg), "Reported - Temp: %.2f°C, Humidity: %.2f%%", temp, humidity);
        log_message("INFO", msg);
    }
    
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return 0;
}

// Log message with timestamp
void log_message(const char* level, const char* message) {
    time_t now = time(NULL);
    char timestamp[64];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", localtime(&now));
    printf("[%s] [%s] %s\n", timestamp, level, message);
}

// Print usage information
void print_usage(const char* program) {
    printf("Karyx IoT Sensor Firmware v%s\n\n", VERSION);
    printf("Usage: %s [OPTIONS]\n\n", program);
    printf("Options:\n");
    printf("  --config <file>    Configuration file (default: config.ini)\n");
    printf("  --version          Show version information\n");
    printf("  --help             Show this help message\n\n");
    printf("Example:\n");
    printf("  %s --config /etc/karyx/sensor.ini\n\n", program);
}

// Main function
int main(int argc, char *argv[]) {
    const char* config_file = "config.ini";

    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--config") == 0 && i + 1 < argc) {
            config_file = argv[++i];
        } else if (strcmp(argv[i], "--version") == 0) {
            printf("Karyx IoT Sensor Firmware v%s\n", VERSION);
            return 0;
        } else if (strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        }
    }

    // Initialize
    printf("\n╔════════════════════════════════════════╗\n");
    printf("║  Karyx IoT Sensor Firmware v%s      ║\n", VERSION);
    printf("╚════════════════════════════════════════╝\n\n");

    // Load configuration
    log_message("INFO", "Loading configuration...");
    load_config(config_file);

    // Setup signal handlers
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    // Initialize random seed
    srand(time(NULL));

    // Initialize CURL
    curl_global_init(CURL_GLOBAL_DEFAULT);

    // Register device if device_id is empty
    if (strlen(config.device_id) == 0) {
        log_message("INFO", "Registering device with panel...");
        if (register_device() != 0) {
            log_message("ERROR", "Failed to register device");
            curl_global_cleanup();
            return 1;
        }
    }

    log_message("INFO", "Starting sensor monitoring...");
    printf("Device: %s\n", config.device_name);
    printf("Panel: %s\n", config.panel_url);
    printf("Interval: %d seconds\n\n", config.report_interval);

    // Main loop
    int cycle = 0;
    while (running) {
        cycle++;
        
        // Read sensors
        float temperature = read_temperature();
        float humidity = read_humidity();

        printf("[Cycle %d] Temp: %.2f°C | Humidity: %.2f%%\n", 
               cycle, temperature, humidity);

        // Report to panel
        report_metrics(temperature, humidity);

        // Sleep for configured interval
        for (int i = 0; i < config.report_interval && running; i++) {
            sleep(1);
        }
    }

    // Cleanup
    log_message("INFO", "Shutting down sensor firmware...");
    curl_global_cleanup();

    printf("\n╔════════════════════════════════════════╗\n");
    printf("║  Sensor Firmware Stopped              ║\n");
    printf("╚════════════════════════════════════════╝\n\n");

    return 0;
}
