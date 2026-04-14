// ============================================================================
// esp32_ae_monitor.ino
//
// Minimal firmware for the microfracture harvesting prototype. Reads two
// channels from the Sovereign rectifier board:
//
//   1. Continuous hysteresis voltage across C1 (rectified PVDF output), read
//      through a 100k/10k divider on the ESP32 ADC.
//   2. AE (acoustic emission) spike events, read as a falling-edge interrupt
//      from the TLV3201 comparator's open-drain output.
//
// The sketch prints C1 voltage and cumulative spike count to Serial once per
// second. Each spike triggers the interrupt service routine (ISR) which
// increments a volatile counter.
//
// Pin choices assume a classic ESP32 DevKit (ESP-WROOM-32). On ESP32-C3,
// ADC1 pins are GPIO0..GPIO4, so change HYST_ADC_PIN and SPIKE_GPIO
// accordingly before flashing.
// ============================================================================

#define HYST_ADC_PIN  34   // ADC1_CH6 on classic ESP32. Change for C3.
#define SPIKE_GPIO    18   // any GPIO capable of external interrupt

// Voltage divider: 100k top, 10k bottom => ratio 1/11 (V_div = V_C1 / 11)
const float DIVIDER_RATIO = 11.0f;
const float ADC_REF       = 3.3f;
const int   ADC_MAX       = 4095;   // 12-bit

volatile unsigned long spikeCount = 0;

void IRAM_ATTR onSpike() {
    spikeCount++;
}

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println();
    Serial.println("Microfracture harvest monitor starting");

    pinMode(SPIKE_GPIO, INPUT_PULLUP);  // internal pull-up (external 10k OK too)
    attachInterrupt(digitalPinToInterrupt(SPIKE_GPIO), onSpike, FALLING);

    analogReadResolution(12);
}

void loop() {
    int adcVal = analogRead(HYST_ADC_PIN);
    float vDiv = adcVal * (ADC_REF / ADC_MAX);
    float vC1  = vDiv * DIVIDER_RATIO;

    static unsigned long lastPrint = 0;
    if (millis() - lastPrint > 1000) {
        lastPrint = millis();

        // Latch spike count atomically
        noInterrupts();
        unsigned long spikes = spikeCount;
        interrupts();

        Serial.print("C1=");
        Serial.print(vC1, 3);
        Serial.print(" V   spikes=");
        Serial.println(spikes);
    }
}
