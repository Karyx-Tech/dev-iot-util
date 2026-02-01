/*
 * Karyx IoT Switch Firmware
 * 
 * CLI-based switch/actuator firmware that controls relays and receives
 * commands from the Karyx IoT Panel via HTTP API
 * 
 * Compile: make
 * Usage: ./switch_firmware --config config.ini
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include <pthread.h>
#include <curl/curl.h>
#include <sys/sysinfo.h>

#define VERSION "1.0.0"
#define MAX_BUFFER 2048
#define CONFIG_LINE_MAX 256
#define MAX_CHANNELS 4

// Configuration structure
typedef struct {
    char device_id[64];
    char device_name[128];
    char panel_url[256];
    int report_interval;
    int poll_commands_interval;
    int num_channels;
    int verbose;
} Config;

// Switch state structure
typedef struct {
    int channel[MAX_CHANNELS];
    time_t last_toggle[MAX_CHANNELS];
    unsigned long toggle_count[MAX_CHANNELS];
} SwitchState;

// Global variables
static volatile int running = 1;
static Config config;
static SwitchState switch_state = {0};
static pthread_mutex_t state_mutex = PTHREAD_MUTEX_INITIALIZER;

// Function prototypes
void signal_handler(int signum);
void load_config(const char* filename);
void* command_listener_thread(void* arg);
int register_device();
int report_status();
int poll_commands();
void execute_command(const char* command, int channel);
void set_switch(int channel, int state);
int get_switch(int channel);
void toggle_switch(int channel);
size_t write_callback(void *contents, size_t size, size_t nmemb, void *userp);
void print_usage(const char* program);
void log_message(const char* level, const char* message);
void print_status();

// Signal handler
void signal_handler(int signum) {
    log_message("INFO", "Received shutdown signal");
    running = 0;
}

// Load configuration
void load_config(const char* filename) {
    FILE* file = fopen(filename, "r");
    if (!file) {
        fprintf(stderr, "Error: Cannot open config file: %s\n", filename);
        exit(1);
    }

    // Set defaults
    config.num_channels = 4;
    config.poll_commands_interval = 5;

    char line[CONFIG_LINE_MAX];
    while (fgets(line, sizeof(line), file)) {
        if (line[0] == '#' || line[0] == '\n') continue;

        char key[64], value[192];
        if (sscanf(line, "%63[^=]=%191[^\n]", key, value) == 2) {
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
            } else if (strcmp(k, "num_channels") == 0) {
                config.num_channels = atoi(v);
                if (config.num_channels > MAX_CHANNELS) {
                    config.num_channels = MAX_CHANNELS;
                }
            } else if (strcmp(k, "verbose") == 0) {
                config.verbose = atoi(v);
            }
        }
    }

    fclose(file);
}

// CURL write callback
size_t write_callback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    char* buffer = (char*)userp;
    strncat(buffer, contents, realsize);
    return realsize;
}

// Register device
int register_device() {
    CURL *curl;
    CURLcode res;
    char url[512];
    char response[MAX_BUFFER] = {0};
    char post_data[MAX_BUFFER];

    snprintf(url, sizeof(url), "%s/devices", config.panel_url);
    snprintf(post_data, sizeof(post_data),
        "{\"name\":\"%s\",\"device_type\":\"switch\",\"ip_address\":\"127.0.0.1\",\"metadata\":{\"firmware_version\":\"%s\",\"channels\":%d}}",
        config.device_name, VERSION, config.num_channels);

    curl = curl_easy_init();
    if (!curl) return -1;

    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, post_data);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);

    res = curl_easy_perform(curl);
    
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    
    return (res == CURLE_OK) ? 0 : -1;
}

// Set switch state
void set_switch(int channel, int state) {
    if (channel < 0 || channel >= config.num_channels) return;
    
    pthread_mutex_lock(&state_mutex);
    
    if (switch_state.channel[channel] != state) {
        switch_state.channel[channel] = state;
        switch_state.last_toggle[channel] = time(NULL);
        switch_state.toggle_count[channel]++;
        
        // In real firmware, this would control actual GPIO pins
        // For example: gpio_write(channel, state);
        
        if (config.verbose) {
            char msg[128];
            snprintf(msg, sizeof(msg), "Channel %d: %s", channel, state ? "ON" : "OFF");
            log_message("INFO", msg);
        }
    }
    
    pthread_mutex_unlock(&state_mutex);
}

// Get switch state
int get_switch(int channel) {
    if (channel < 0 || channel >= config.num_channels) return 0;
    
    pthread_mutex_lock(&state_mutex);
    int state = switch_state.channel[channel];
    pthread_mutex_unlock(&state_mutex);
    
    return state;
}

// Toggle switch
void toggle_switch(int channel) {
    int current = get_switch(channel);
    set_switch(channel, !current);
}

// Execute command
void execute_command(const char* command, int channel) {
    char msg[128];
    snprintf(msg, sizeof(msg), "Command: %s on channel %d", command, channel);
    log_message("INFO", msg);

    if (strcmp(command, "on") == 0) {
        set_switch(channel, 1);
    } else if (strcmp(command, "off") == 0) {
        set_switch(channel, 0);
    } else if (strcmp(command, "toggle") == 0) {
        toggle_switch(channel);
    } else if (strcmp(command, "status") == 0) {
        print_status();
    } else if (strcmp(command, "all_on") == 0) {
        for (int i = 0; i < config.num_channels; i++) {
            set_switch(i, 1);
        }
    } else if (strcmp(command, "all_off") == 0) {
        for (int i = 0; i < config.num_channels; i++) {
            set_switch(i, 0);
        }
    }
}

// Report status to panel
int report_status() {
    CURL *curl;
    CURLcode res;
    char url[512];
    char response[MAX_BUFFER] = {0};
    char post_data[MAX_BUFFER];
    char channels_data[256] = {0};

    // Build channels state string
    strcat(channels_data, "[");
    for (int i = 0; i < config.num_channels; i++) {
        char ch[16];
        snprintf(ch, sizeof(ch), "%d%s", get_switch(i), (i < config.num_channels - 1) ? "," : "");
        strcat(channels_data, ch);
    }
    strcat(channels_data, "]");

    snprintf(url, sizeof(url), "%s/devices/%s", config.panel_url, config.device_id);
    snprintf(post_data, sizeof(post_data),
        "{\"status\":\"online\",\"metrics\":{\"channels\":%s,\"total_toggles\":%lu}}",
        channels_data, switch_state.toggle_count[0] + switch_state.toggle_count[1]);

    curl = curl_easy_init();
    if (!curl) return -1;

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
    
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    
    return (res == CURLE_OK) ? 0 : -1;
}

// Print current status
void print_status() {
    printf("\n┌──────────────────────────────┐\n");
    printf("│   Switch Status           │\n");
    printf("├──────────────────────────────┤\n");
    
    for (int i = 0; i < config.num_channels; i++) {
        pthread_mutex_lock(&state_mutex);
        int state = switch_state.channel[i];
        unsigned long count = switch_state.toggle_count[i];
        pthread_mutex_unlock(&state_mutex);
        
        printf("│ CH%d: [%s] (%lu toggles) │\n", 
               i, state ? "ON " : "OFF", count);
    }
    
    printf("└──────────────────────────────┘\n\n");
}

// Command listener thread (simulated)
void* command_listener_thread(void* arg) {
    (void)arg;
    log_message("INFO", "Command listener thread started");
    
    while (running) {
        // In real firmware, this would poll the panel for commands
        // or listen to MQTT/WebSocket for real-time commands
        sleep(config.poll_commands_interval);
    }
    
    return NULL;
}

// Log message
void log_message(const char* level, const char* message) {
    time_t now = time(NULL);
    char timestamp[64];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", localtime(&now));
    printf("[%s] [%s] %s\n", timestamp, level, message);
}

// Print usage
void print_usage(const char* program) {
    printf("Karyx IoT Switch Firmware v%s\n\n", VERSION);
    printf("Usage: %s [OPTIONS]\n\n", program);
    printf("Options:\n");
    printf("  --config <file>    Configuration file (default: config.ini)\n");
    printf("  --version          Show version information\n");
    printf("  --help             Show this help message\n\n");
    printf("Interactive Commands:\n");
    printf("  on <ch>            Turn on channel\n");
    printf("  off <ch>           Turn off channel\n");
    printf("  toggle <ch>        Toggle channel\n");
    printf("  status             Show switch status\n");
    printf("  quit               Exit program\n\n");
}

// Main function
int main(int argc, char *argv[]) {
    const char* config_file = "config.ini";

    // Parse arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--config") == 0 && i + 1 < argc) {
            config_file = argv[++i];
        } else if (strcmp(argv[i], "--version") == 0) {
            printf("Karyx IoT Switch Firmware v%s\n", VERSION);
            return 0;
        } else if (strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        }
    }

    // Initialize
    printf("\n╔════════════════════════════════════════╗\n");
    printf("║  Karyx IoT Switch Firmware v%s      ║\n", VERSION);
    printf("╚════════════════════════════════════════╝\n\n");

    load_config(config_file);
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    curl_global_init(CURL_GLOBAL_DEFAULT);

    if (strlen(config.device_id) == 0) {
        log_message("INFO", "Registering device...");
        register_device();
    }

    log_message("INFO", "Starting switch firmware...");
    printf("Device: %s\n", config.device_name);
    printf("Channels: %d\n", config.num_channels);
    printf("Type 'help' for commands\n\n");

    // Start command listener thread
    pthread_t listener_thread;
    pthread_create(&listener_thread, NULL, command_listener_thread, NULL);

    // Main loop - CLI interface
    char input[128];
    while (running) {
        printf("> ");
        fflush(stdout);
        
        if (fgets(input, sizeof(input), stdin) == NULL) break;
        
        // Remove newline
        input[strcspn(input, "\n")] = 0;
        
        if (strlen(input) == 0) continue;
        
        char cmd[32];
        int channel = 0;
        sscanf(input, "%s %d", cmd, &channel);
        
        if (strcmp(cmd, "quit") == 0 || strcmp(cmd, "exit") == 0) {
            running = 0;
        } else if (strcmp(cmd, "status") == 0) {
            print_status();
        } else if (strcmp(cmd, "help") == 0) {
            printf("Commands: on <ch>, off <ch>, toggle <ch>, status, quit\n");
        } else {
            execute_command(cmd, channel);
        }
        
        // Report status periodically
        static time_t last_report = 0;
        if (time(NULL) - last_report >= config.report_interval) {
            report_status();
            last_report = time(NULL);
        }
    }

    // Cleanup
    log_message("INFO", "Shutting down...");
    pthread_join(listener_thread, NULL);
    curl_global_cleanup();

    printf("\n╔════════════════════════════════════════╗\n");
    printf("║  Switch Firmware Stopped              ║\n");
    printf("╚════════════════════════════════════════╝\n\n");

    return 0;
}
