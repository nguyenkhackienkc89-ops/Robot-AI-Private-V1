#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "display/lcd_display.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "mcp_server.h"
#include "settings.h"
#include "led/single_led.h"

#include <esp_log.h>
#include <esp_timer.h>
#include <esp_system.h>
#include <esp_lcd_panel_vendor.h>
#include <esp_lcd_panel_io.h>
#include <esp_lcd_panel_ops.h>
#include <esp_http_client.h>
#include <esp_http_server.h>

#include <driver/spi_common.h>
#include <driver/ledc.h>
#include <driver/gpio.h>
#include <driver/i2c_master.h>

#include <nvs.h>
#include <nvs_flash.h>

#include <lwip/sockets.h>
#include <lwip/inet.h>

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <atomic>
#include <algorithm>
#include <string>
#include <cstring>
#include <cstdlib>
#include <unistd.h>

#define TAG "RobotPrivateV1"

enum class RobotFace : int {
    Idle = 0, Listening, Speaking, Thinking, Teasing, Surprise, Angry, Music
};

class RobotFaceDisplay : public SpiLcdDisplay {
public:
    RobotFaceDisplay(esp_lcd_panel_io_handle_t io_handle,
                     esp_lcd_panel_handle_t panel_handle,
                     int width, int height, int offset_x, int offset_y,
                     bool mirror_x, bool mirror_y, bool swap_xy)
        : SpiLcdDisplay(io_handle, panel_handle, width, height,
                        offset_x, offset_y, mirror_x, mirror_y, swap_xy) {}

    void SetupUI() override {
        SpiLcdDisplay::SetupUI();
        DisplayLockGuard lock(this);

        lv_obj_set_size(emoji_box_, 190, 92);
        lv_obj_align(emoji_box_, LV_ALIGN_CENTER, 0, -18);

        face_layer_ = lv_obj_create(emoji_box_);
        lv_obj_remove_style_all(face_layer_);
        lv_obj_set_size(face_layer_, 188, 90);
        lv_obj_center(face_layer_);
        lv_obj_set_style_bg_color(face_layer_, lv_color_hex(0x000000), 0);
        lv_obj_set_style_bg_opa(face_layer_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(face_layer_, LV_OBJ_FLAG_SCROLLABLE);

        left_ = lv_obj_create(face_layer_);
        right_ = lv_obj_create(face_layer_);
        PrepareEye(left_);
        PrepareEye(right_);
        for (int k=0;k<8;k++) {
            bars_[k] = lv_obj_create(face_layer_);
            lv_obj_remove_style_all(bars_[k]);
            lv_obj_set_style_bg_opa(bars_[k], LV_OPA_COVER, 0);
            lv_obj_set_style_bg_color(bars_[k], lv_color_hex(0xBFEAFF), 0);
            lv_obj_set_style_radius(bars_[k], 3, 0);
            lv_obj_add_flag(bars_[k], LV_OBJ_FLAG_HIDDEN);
        }
        DrawUnlocked(RobotFace::Idle, false);
    }

    void Request(RobotFace face) { requested_.store(static_cast<int>(face)); }

    void Manual(RobotFace face, int ms = 2500) {
        manual_.store(static_cast<int>(face));
        manual_until_us_.store(esp_timer_get_time() + (int64_t)ms * 1000);
    }

    void Tick(bool blink) {
        DisplayLockGuard lock(this);
        RobotFace f = static_cast<RobotFace>(requested_.load());
        if (esp_timer_get_time() < manual_until_us_.load())
            f = static_cast<RobotFace>(manual_.load());
        DrawUnlocked(f, blink);
    }

private:
    lv_obj_t* face_layer_ = nullptr;
    lv_obj_t* left_ = nullptr;
    lv_obj_t* right_ = nullptr;
    lv_obj_t* bars_[8] = {nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr};
    std::atomic<int> requested_{0};
    std::atomic<int> manual_{0};
    std::atomic<int64_t> manual_until_us_{0};
    int frame_ = 0;

    static void PrepareEye(lv_obj_t* o) {
        lv_obj_remove_style_all(o);
        lv_obj_set_style_bg_opa(o, LV_OPA_COVER, 0);
        lv_obj_set_style_border_width(o, 0, 0);
        lv_obj_clear_flag(o, LV_OBJ_FLAG_SCROLLABLE);
    }

    void DrawUnlocked(RobotFace face, bool blink) {
        if (!left_ || !right_) return;
        ++frame_;

        if (face == RobotFace::Music) {
            lv_obj_add_flag(left_, LV_OBJ_FLAG_HIDDEN);
            lv_obj_add_flag(right_, LV_OBJ_FLAG_HIDDEN);
            for (int k=0;k<8;k++) {
                lv_obj_clear_flag(bars_[k], LV_OBJ_FLAG_HIDDEN);
                int phase=(frame_ + k*3) % 18;
                int hh=12 + ((phase < 9 ? phase : 18-phase) * 6);
                lv_obj_set_size(bars_[k], 12, hh);
                lv_obj_align(bars_[k], LV_ALIGN_CENTER, -70 + k*20, 18 - hh/2);
            }
            return;
        }
        lv_obj_clear_flag(left_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(right_, LV_OBJ_FLAG_HIDDEN);
        for (int k=0;k<8;k++) lv_obj_add_flag(bars_[k], LV_OBJ_FLAG_HIDDEN);

        int w=52, h=30, gap=22, y=0;
        uint32_t color=0xF8FBFF;

        switch(face) {
            case RobotFace::Idle:      w=52; h=26; gap=22; y=1; break;
            case RobotFace::Listening: w=54; h=38; gap=20; y=-1; color=0xBFEAFF; break;
            case RobotFace::Speaking:  w=52; h=22+((frame_/2)%4)*4; gap=22; y=0; break;
            case RobotFace::Thinking:  w=48; h=16; gap=28; y=-4; break;
            case RobotFace::Teasing:   w=52; h=10; gap=24; y=6; break;
            case RobotFace::Surprise:  w=44; h=44; gap=24; y=0; break;
            case RobotFace::Angry:     w=54; h=12; gap=18; y=2; color=0xFFD2D2; break;
            case RobotFace::Music:     break;
        }
        if (blink) h=4;

        for (lv_obj_t* eye : {left_, right_}) {
            lv_obj_set_size(eye, w, h);
            lv_obj_set_style_radius(eye, std::max(2, h/3), 0);
            lv_obj_set_style_bg_color(eye, lv_color_hex(color), 0);
        }
        int half = gap/2 + w/2;
        lv_obj_align(left_, LV_ALIGN_CENTER, -half, y);
        lv_obj_align(right_, LV_ALIGN_CENTER, half, y);
    }
};

class Tof050c {
public:
    bool Init() {
        i2c_master_bus_config_t bus_cfg = {};
        bus_cfg.i2c_port = I2C_NUM_1;
        bus_cfg.sda_io_num = TOF_SDA_PIN;
        bus_cfg.scl_io_num = TOF_SCL_PIN;
        bus_cfg.clk_source = I2C_CLK_SRC_DEFAULT;
        bus_cfg.glitch_ignore_cnt = 7;
        bus_cfg.flags.enable_internal_pullup = true;
        if (i2c_new_master_bus(&bus_cfg, &bus_) != ESP_OK) return false;

        i2c_device_config_t dev_cfg = {};
        dev_cfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;
        dev_cfg.device_address = TOF_I2C_ADDR;
        dev_cfg.scl_speed_hz = 400000;
        if (i2c_master_bus_add_device(bus_, &dev_cfg, &dev_) != ESP_OK) return false;

        uint8_t model = 0;
        if (!Read8(0x0000, model)) return false;
        ESP_LOGI(TAG, "VL6180X model=0x%02x", model);

        if (!LoadSettings()) return false;
        Write8(0x0016, 0x00);
        ready_.store(true);

        xTaskCreate([](void* p){ static_cast<Tof050c*>(p)->Loop(); },
                    "tof050c", 4096, this, 3, &task_);
        return true;
    }

    int DistanceMm() const { return mm_.load(); }
    bool Ready() const { return ready_.load(); }

private:
    i2c_master_bus_handle_t bus_ = nullptr;
    i2c_master_dev_handle_t dev_ = nullptr;
    TaskHandle_t task_ = nullptr;
    std::atomic<int> mm_{-1};
    std::atomic<bool> ready_{false};

    bool Write8(uint16_t reg, uint8_t val) {
        uint8_t tx[3] = {(uint8_t)(reg>>8), (uint8_t)reg, val};
        return i2c_master_transmit(dev_, tx, sizeof(tx), 100) == ESP_OK;
    }
    bool Read8(uint16_t reg, uint8_t& val) {
        uint8_t a[2] = {(uint8_t)(reg>>8), (uint8_t)reg};
        return i2c_master_transmit_receive(dev_, a, 2, &val, 1, 100) == ESP_OK;
    }
    bool LoadSettings() {
        static const struct { uint16_t r; uint8_t v; } s[] = {
            {0x0207,0x01},{0x0208,0x01},{0x0096,0x00},{0x0097,0xFD},
            {0x00E3,0x00},{0x00E4,0x04},{0x00E5,0x02},{0x00E6,0x01},
            {0x00E7,0x03},{0x00F5,0x02},{0x00D9,0x05},{0x00DB,0xCE},
            {0x00DC,0x03},{0x00DD,0xF8},{0x009F,0x00},{0x00A3,0x3C},
            {0x00B7,0x00},{0x00BB,0x3C},{0x00B2,0x09},{0x00CA,0x09},
            {0x0198,0x01},{0x01B0,0x17},{0x01AD,0x00},{0x00FF,0x05},
            {0x0100,0x05},{0x0199,0x05},{0x01A6,0x1B},{0x01AC,0x3E},
            {0x01A7,0x1F},{0x0030,0x00},{0x0011,0x10},{0x010A,0x30},
            {0x003F,0x46},{0x0031,0xFF},{0x0041,0x63},{0x002E,0x01},
            {0x001B,0x09},{0x003E,0x31},{0x0014,0x24}
        };
        for (auto& x : s) if (!Write8(x.r, x.v)) return false;
        return true;
    }
    int Measure() {
        uint8_t status=0;
        for (int i=0;i<25;i++) {
            if (!Read8(0x004D,status)) return -1;
            if (status & 0x01) break;
            vTaskDelay(pdMS_TO_TICKS(2));
        }
        if (!(status & 0x01)) return -1;
        if (!Write8(0x0018,0x01)) return -1;

        uint8_t irq=0;
        for (int i=0;i<50;i++) {
            if (!Read8(0x004F,irq)) return -1;
            if (irq & 0x04) break;
            vTaskDelay(pdMS_TO_TICKS(2));
        }
        if (!(irq & 0x04)) return -1;
        uint8_t mm=0;
        if (!Read8(0x0062,mm)) return -1;
        Write8(0x0015,0x07);
        return (int)mm;
    }
    void Loop() {
        for (;;) {
            mm_.store(Measure());
            vTaskDelay(pdMS_TO_TICKS(80));
        }
    }
};

class MotorController {
public:
    void Init(Tof050c* tof) {
        tof_ = tof;
        LoadCalibration();

        ledc_timer_config_t timer = {};
        timer.speed_mode = LEDC_LOW_SPEED_MODE;
        timer.duty_resolution = LEDC_TIMER_10_BIT;
        timer.timer_num = LEDC_TIMER_2;
        timer.freq_hz = MOTOR_PWM_HZ;
        timer.clk_cfg = LEDC_AUTO_CLK;
        ESP_ERROR_CHECK(ledc_timer_config(&timer));

        SetupChannel(MOTOR_LEFT_IN1,  LEDC_CHANNEL_4);
        SetupChannel(MOTOR_LEFT_IN2,  LEDC_CHANNEL_5);
        SetupChannel(MOTOR_RIGHT_IN1, LEDC_CHANNEL_6);
        SetupChannel(MOTOR_RIGHT_IN2, LEDC_CHANNEL_7);

        Stop();
        xTaskCreate([](void* p){ static_cast<MotorController*>(p)->Loop(); },
                    "motor_guard", 4096, this, 5, &task_);
    }

    void Forward(int speed, int ms) {
        speed = ClampSpeed(speed);
        ms = std::clamp(ms, 80, MOTOR_MAX_LINEAR_MS);
        Command(speed, speed, ms, true);
    }
    void Backward(int speed, int ms) {
        speed = ClampSpeed(speed);
        ms = std::clamp(ms, 80, MOTOR_MAX_LINEAR_MS);
        Command(-speed, -speed, ms, false);
    }
    void TurnLeft(int speed, int ms) {
        speed = ClampTurn(speed);
        ms = std::clamp(ms, 80, MOTOR_MAX_TURN_MS);
        Command(-speed, speed, ms, false);
    }
    void TurnRight(int speed, int ms) {
        speed = ClampTurn(speed);
        ms = std::clamp(ms, 80, MOTOR_MAX_TURN_MS);
        Command(speed, -speed, ms, false);
    }
    void Spin360(bool right) {
        int ms = spin360_ms_.load();
        int s = MOTOR_TURN_SPEED;
        if (right) Command(s,-s,ms,false);
        else Command(-s,s,ms,false);
    }
    void Wiggle() {
        struct Ctx { MotorController* s; };
        auto* c = new Ctx{this};
        xTaskCreate([](void* p){
            auto* c=static_cast<Ctx*>(p);
            c->s->TurnLeft(28,130); vTaskDelay(pdMS_TO_TICKS(170));
            c->s->TurnRight(28,130); vTaskDelay(pdMS_TO_TICKS(170));
            c->s->TurnLeft(24,90); vTaskDelay(pdMS_TO_TICKS(120));
            c->s->Stop(); delete c; vTaskDelete(nullptr);
        },"wiggle",3072,c,3,nullptr);
    }
    void Dance() {
        struct Ctx { MotorController* s; };
        auto* c = new Ctx{this};
        xTaskCreate([](void* p){
            auto* c=static_cast<Ctx*>(p);
            c->s->TurnLeft(38,260);  vTaskDelay(pdMS_TO_TICKS(300));
            c->s->TurnRight(38,520); vTaskDelay(pdMS_TO_TICKS(560));
            c->s->TurnLeft(38,260);  vTaskDelay(pdMS_TO_TICKS(300));
            c->s->Forward(30,220);   vTaskDelay(pdMS_TO_TICKS(260));
            c->s->Backward(30,220);  vTaskDelay(pdMS_TO_TICKS(260));
            c->s->Stop();
            delete c;
            vTaskDelete(nullptr);
        },"robot_dance",4096,c,3,nullptr);
    }
    void Stop() {
        left_.store(0); right_.store(0); deadline_us_.store(0);
        Apply(0,0);
    }
    void SetSpin360Ms(int ms) {
        ms = std::clamp(ms, 600, 3000);
        spin360_ms_.store(ms);
        nvs_handle_t h;
        if (nvs_open("robot_cal", NVS_READWRITE, &h)==ESP_OK) {
            nvs_set_i32(h,"spin360_ms",ms); nvs_commit(h); nvs_close(h);
        }
    }
    int Spin360Ms() const { return spin360_ms_.load(); }
    void SetStopDistanceMm(int mm) {
        mm = std::clamp(mm, 60, 500);
        stop_distance_mm_.store(mm);
        nvs_handle_t h;
        if (nvs_open("robot_cal", NVS_READWRITE, &h)==ESP_OK) {
            nvs_set_i32(h,"stop_mm",mm); nvs_commit(h); nvs_close(h);
        }
    }
    int StopDistanceMm() const { return stop_distance_mm_.load(); }

private:
    Tof050c* tof_=nullptr;
    TaskHandle_t task_=nullptr;
    std::atomic<int> left_{0}, right_{0};
    std::atomic<int64_t> deadline_us_{0};
    std::atomic<bool> check_front_{false};
    std::atomic<int> spin360_ms_{MOTOR_SPIN_360_DEFAULT_MS};
    std::atomic<int> stop_distance_mm_{MOTOR_STOP_DISTANCE_MM};
    int applied_l_=999, applied_r_=999;

    static int ClampSpeed(int x){ return std::clamp(x,20,60); }
    static int ClampTurn(int x){ return std::clamp(x,20,65); }
    static void SetupChannel(gpio_num_t pin, ledc_channel_t ch) {
        ledc_channel_config_t c={};
        c.gpio_num=pin; c.speed_mode=LEDC_LOW_SPEED_MODE; c.channel=ch;
        c.intr_type=LEDC_INTR_DISABLE; c.timer_sel=LEDC_TIMER_2;
        ESP_ERROR_CHECK(ledc_channel_config(&c));
    }
    static uint32_t Duty(int speed){
        return (uint32_t)(MOTOR_MAX_DUTY*std::clamp(std::abs(speed),0,100)/100);
    }
    static void MotorOut(ledc_channel_t a, ledc_channel_t b, int s, int polarity){
        s*=polarity;
        uint32_t d=Duty(s), da=0, db=0;
        if(s>0) da=d; else if(s<0) db=d;
        ledc_set_duty(LEDC_LOW_SPEED_MODE,a,da); ledc_update_duty(LEDC_LOW_SPEED_MODE,a);
        ledc_set_duty(LEDC_LOW_SPEED_MODE,b,db); ledc_update_duty(LEDC_LOW_SPEED_MODE,b);
    }
    void Apply(int l,int r){
        if(l==applied_l_ && r==applied_r_) return;
        MotorOut(LEDC_CHANNEL_4,LEDC_CHANNEL_5,l,MOTOR_LEFT_POLARITY);
        MotorOut(LEDC_CHANNEL_6,LEDC_CHANNEL_7,r,MOTOR_RIGHT_POLARITY);
        applied_l_=l; applied_r_=r;
    }
    void Command(int l,int r,int ms,bool front_guard){
        left_.store(l); right_.store(r); check_front_.store(front_guard);
        deadline_us_.store(esp_timer_get_time()+(int64_t)ms*1000);
    }
    void LoadCalibration(){
        nvs_handle_t h; int32_t v=MOTOR_SPIN_360_DEFAULT_MS;
        if(nvs_open("robot_cal",NVS_READONLY,&h)==ESP_OK){
            if(nvs_get_i32(h,"spin360_ms",&v)==ESP_OK)
                spin360_ms_.store(std::clamp((int)v,600,3000));
            int32_t stop_mm=MOTOR_STOP_DISTANCE_MM;
            if(nvs_get_i32(h,"stop_mm",&stop_mm)==ESP_OK)
                stop_distance_mm_.store(std::clamp((int)stop_mm,60,500));
            nvs_close(h);
        }
    }
    void Loop(){
        for(;;){
            int l=left_.load(), r=right_.load();
            int64_t now=esp_timer_get_time(), dl=deadline_us_.load();
            if(dl && now>=dl){
                l=r=0; left_.store(0); right_.store(0); deadline_us_.store(0);
            }
            if(check_front_.load() && l>0 && r>0 && tof_ && tof_->Ready()){
                int mm=tof_->DistanceMm();
                if(mm>0 && mm<stop_distance_mm_.load()){
                    ESP_LOGW(TAG,"Obstacle %d mm -> STOP",mm);
                    l=r=0; left_.store(0); right_.store(0); deadline_us_.store(0);
                }
            }
            Apply(l,r);
            vTaskDelay(pdMS_TO_TICKS(20));
        }
    }
};

class RobotLights {
public:
    void Init(){
        gpio_config_t c={};
        c.pin_bit_mask=(1ULL<<ROBOT_LED_A_GPIO)|(1ULL<<ROBOT_LED_B_GPIO);
        c.mode=GPIO_MODE_OUTPUT;
        ESP_ERROR_CHECK(gpio_config(&c));
        Set(false,false);
    }
    void Set(bool a,bool b){
        gpio_set_level(ROBOT_LED_A_GPIO,a);
        gpio_set_level(ROBOT_LED_B_GPIO,b);
    }
};

class MacBridgeClient {
public:
    bool Discover(){
        int sock=socket(AF_INET,SOCK_DGRAM,IPPROTO_IP);
        if(sock<0) return false;
        int yes=1;
        setsockopt(sock,SOL_SOCKET,SO_BROADCAST,&yes,sizeof(yes));
        struct timeval tv={1,0};
        setsockopt(sock,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));

        sockaddr_in dst={};
        dst.sin_family=AF_INET;
        dst.sin_port=htons(MAC_BRIDGE_DISCOVERY_PORT);
        dst.sin_addr.s_addr=inet_addr("255.255.255.255");

        std::string msg=std::string("ROBOT_DISCOVER ")+MAC_BRIDGE_TOKEN;
        sendto(sock,msg.data(),msg.size(),0,(sockaddr*)&dst,sizeof(dst));

        char buf[160]={0};
        sockaddr_in src={}; socklen_t sl=sizeof(src);
        int n=recvfrom(sock,buf,sizeof(buf)-1,0,(sockaddr*)&src,&sl);
        close(sock);
        if(n<=0) return false;
        buf[n]=0;
        std::string reply(buf);
        std::string expected=std::string("ROBOT_MAC ")+MAC_BRIDGE_TOKEN;
        if(reply.rfind(expected,0)!=0) return false;

        char ip[INET_ADDRSTRLEN]={0};
        inet_ntop(AF_INET,&src.sin_addr,ip,sizeof(ip));
        host_=ip;
        return true;
    }

    bool Call(const std::string& action, const std::string& value=""){
        if(host_.empty() && !Discover()) return false;
        std::string url="http://"+host_+":"+std::to_string(MAC_BRIDGE_HTTP_PORT)+"/command";
        std::string body="{\"action\":\""+JsonEscape(action)+"\",\"value\":\""+JsonEscape(value)+"\"}";

        esp_http_client_config_t cfg={};
        cfg.url=url.c_str();
        cfg.method=HTTP_METHOD_POST;
        cfg.timeout_ms=5000;
        esp_http_client_handle_t c=esp_http_client_init(&cfg);
        if(!c) return false;

        esp_http_client_set_header(c,"Content-Type","application/json");
        esp_http_client_set_header(c,"X-Robot-Token",MAC_BRIDGE_TOKEN);
        esp_http_client_set_post_field(c,body.data(),body.size());
        esp_err_t err=esp_http_client_perform(c);
        int status=esp_http_client_get_status_code(c);
        esp_http_client_cleanup(c);
        if(err!=ESP_OK || status<200 || status>=300){
            host_.clear();
            return false;
        }
        return true;
    }

private:
    std::string host_;
    static std::string JsonEscape(const std::string& s){
        std::string o; o.reserve(s.size()+8);
        for(char c:s){
            if(c=='\\'||c=='"'){o+='\\';o+=c;}
            else if(c=='\n')o+="\\n";
            else if(c=='\r')o+="\\r";
            else o+=c;
        }
        return o;
    }
};


class RobotAdminUdp {
public:
    void Init(MotorController* motors, Tof050c* tof) {
        motors_ = motors;
        tof_ = tof;
        xTaskCreate([](void* p){ static_cast<RobotAdminUdp*>(p)->ListenLoop(); },
                    "robot_admin", 4096, this, 3, &listen_task_);
        xTaskCreate([](void* p){ static_cast<RobotAdminUdp*>(p)->HelloLoop(); },
                    "robot_hello", 3072, this, 2, &hello_task_);
    }

private:
    MotorController* motors_ = nullptr;
    Tof050c* tof_ = nullptr;
    TaskHandle_t listen_task_ = nullptr;
    TaskHandle_t hello_task_ = nullptr;

    static bool StartsWith(const std::string& s, const std::string& p) {
        return s.rfind(p, 0) == 0;
    }

    std::string Handle(const std::string& cmd) {
        const std::string prefix = std::string("ROBOT_ADMIN ") + MAC_BRIDGE_TOKEN + " ";
        if (!StartsWith(cmd, prefix)) return "ERR auth";
        std::string rest = cmd.substr(prefix.size());

        if (rest == "STATUS") {
            int dist = (tof_ && tof_->Ready()) ? tof_->DistanceMm() : -1;
            return "OK distance_mm=" + std::to_string(dist) +
                   " spin360_ms=" + std::to_string(motors_->Spin360Ms()) +
                   " stop_mm=" + std::to_string(motors_->StopDistanceMm());
        }
        if (StartsWith(rest, "SET_SPIN ")) {
            int v = atoi(rest.substr(9).c_str());
            motors_->SetSpin360Ms(v);
            return "OK spin360_ms=" + std::to_string(motors_->Spin360Ms());
        }
        if (StartsWith(rest, "SET_STOP ")) {
            int v = atoi(rest.substr(9).c_str());
            motors_->SetStopDistanceMm(v);
            return "OK stop_mm=" + std::to_string(motors_->StopDistanceMm());
        }
        if (rest == "STOP") {
            motors_->Stop();
            return "OK stopped";
        }
        if (StartsWith(rest, "MOVE ")) {
            // MOVE action speed duration_ms
            char action[24] = {0};
            int speed = 35, ms = 300;
            if (sscanf(rest.c_str(), "MOVE %23s %d %d", action, &speed, &ms) != 3)
                return "ERR move_args";

            std::string a(action);
            if (a == "forward") motors_->Forward(speed, ms);
            else if (a == "backward") motors_->Backward(speed, ms);
            else if (a == "left") motors_->TurnLeft(speed, ms);
            else if (a == "right") motors_->TurnRight(speed, ms);
            else if (a == "spin_right") motors_->Spin360(true);
            else if (a == "spin_left") motors_->Spin360(false);
            else return "ERR move_action";
            return "OK moving";
        }
        return "ERR unknown";
    }

    void ListenLoop() {
        int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
        if (sock < 0) { vTaskDelete(nullptr); return; }

        sockaddr_in addr = {};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(ROBOT_ADMIN_PORT);
        addr.sin_addr.s_addr = htonl(INADDR_ANY);

        if (bind(sock, (sockaddr*)&addr, sizeof(addr)) < 0) {
            close(sock); vTaskDelete(nullptr); return;
        }

        for (;;) {
            char buf[256] = {0};
            sockaddr_in src = {};
            socklen_t sl = sizeof(src);
            int n = recvfrom(sock, buf, sizeof(buf)-1, 0, (sockaddr*)&src, &sl);
            if (n <= 0) continue;
            buf[n] = 0;
            std::string reply = Handle(std::string(buf));
            sendto(sock, reply.data(), reply.size(), 0, (sockaddr*)&src, sl);
        }
    }

    void HelloLoop() {
        for (;;) {
            int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
            if (sock >= 0) {
                int yes = 1;
                setsockopt(sock, SOL_SOCKET, SO_BROADCAST, &yes, sizeof(yes));
                sockaddr_in dst = {};
                dst.sin_family = AF_INET;
                dst.sin_port = htons(ROBOT_ADMIN_HELLO_PORT);
                dst.sin_addr.s_addr = inet_addr("255.255.255.255");
                std::string msg = std::string("ROBOT_HELLO ") + MAC_BRIDGE_TOKEN +
                                  " robot-ai-private-v4";
                sendto(sock, msg.data(), msg.size(), 0, (sockaddr*)&dst, sizeof(dst));
                close(sock);
            }
            vTaskDelay(pdMS_TO_TICKS(5000));
        }
    }
};



class RobotDeviceWeb {
public:
    void Init(MotorController* motors, Tof050c* tof) {
        motors_ = motors;
        tof_ = tof;
        instance_ = this;

        httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
        cfg.server_port = 8080;
        cfg.ctrl_port = 32772;
        cfg.max_uri_handlers = 8;
        cfg.stack_size = 6144;

        if (httpd_start(&server_, &cfg) != ESP_OK) {
            ESP_LOGW(TAG, "Robot web control failed to start");
            return;
        }

        Register("/", HTTP_GET, Root);
        Register("/status", HTTP_GET, Status);
        Register("/cmd", HTTP_GET, Command);
        Register("/set", HTTP_GET, Settings);
        ESP_LOGI(TAG, "Robot device web control: port 8080");
    }

private:
    inline static RobotDeviceWeb* instance_ = nullptr;
    httpd_handle_t server_ = nullptr;
    MotorController* motors_ = nullptr;
    Tof050c* tof_ = nullptr;

    void Register(const char* uri, httpd_method_t method, esp_err_t (*handler)(httpd_req_t*)) {
        httpd_uri_t u = {};
        u.uri = uri;
        u.method = method;
        u.handler = handler;
        u.user_ctx = nullptr;
        httpd_register_uri_handler(server_, &u);
    }

    static std::string Query(httpd_req_t* req, const char* key) {
        char q[256] = {0};
        if (httpd_req_get_url_query_str(req, q, sizeof(q)) != ESP_OK) return "";
        char v[96] = {0};
        if (httpd_query_key_value(q, key, v, sizeof(v)) != ESP_OK) return "";
        return v;
    }

    static esp_err_t Root(httpd_req_t* req) {
        static const char page[] = R"HTML(
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tiểu Đệ Robot</title>
<style>
body{font-family:Arial;margin:18px;background:#0c121b;color:#eef6ff}
.card{padding:15px;margin:12px 0;border:1px solid #34506d;border-radius:14px;background:#121d2a}
button,input{font-size:17px;padding:11px;margin:4px;border-radius:9px;border:1px solid #45627f}
button{background:#eaf5ff;color:#0a1724}.stop{background:#ffdddd}
code{color:#bfeaff}
</style></head><body>
<h2>Tiểu Đệ · Robot AI Private V5</h2>
<div class="card">
<b>Điều khiển động cơ</b><br>
<button onclick="c('forward')">↑ Tiến</button><br>
<button onclick="c('left')">← Trái</button>
<button class="stop" onclick="c('stop')">■ Dừng</button>
<button onclick="c('right')">Phải →</button><br>
<button onclick="c('backward')">↓ Lùi</button>
<button onclick="c('spin')">↻ 360°</button>
<button onclick="c('dance')">Nhảy</button>
</div>
<div class="card">
<b>Hiệu chuẩn</b><br>
Quay 360: <input id="spin" type="number" value="1700" min="600" max="3000"> ms<br>
Ngưỡng ToF: <input id="stopmm" type="number" value="130" min="60" max="500"> mm<br>
<button onclick="save()">Lưu vào robot</button>
</div>
<div class="card">
<b>Cấu hình phần cứng V2 đã khóa an toàn</b><br>
Màn hình: <code>ST7789 1.3" 240×240</code><br>
ToF050C/VL6180X: <code>SDA41 / SCL42</code><br>
Touch: <code>Tắt</code><br>
LED trang trí: <code>GPIO38 / GPIO46</code><br>
<p>Wi‑Fi & OTA: khi robot đang ở chế độ cấu hình, mở
<a style="color:#bfeaff" href="http://192.168.4.1/">192.168.4.1</a>.</p>
</div>
<div class="card"><b>Trạng thái</b><pre id="s">...</pre></div>
<script>
async function c(m){await fetch('/cmd?m='+m); setTimeout(load,150)}
async function save(){
 await fetch('/set?spin='+encodeURIComponent(spin.value)+'&stop='+encodeURIComponent(stopmm.value));load()
}
async function load(){s.textContent=await (await fetch('/status')).text()}
setInterval(load,1200);load()
</script></body></html>)HTML";
        httpd_resp_set_type(req, "text/html; charset=utf-8");
        return httpd_resp_send(req, page, HTTPD_RESP_USE_STRLEN);
    }

    static esp_err_t Status(httpd_req_t* req) {
        if (!instance_) return ESP_FAIL;
        int d = instance_->tof_ ? instance_->tof_->DistanceMm() : -1;
        std::string body =
            std::string("{\"distance_mm\":") + std::to_string(d) +
            ",\"spin360_ms\":" + std::to_string(instance_->motors_->Spin360Ms()) +
            ",\"stop_mm\":" + std::to_string(instance_->motors_->StopDistanceMm()) +
            ",\"display\":\"ST7789-1.3-240x240\",\"tof\":\"VL6180X\"}";
        httpd_resp_set_type(req, "application/json");
        return httpd_resp_send(req, body.c_str(), body.size());
    }

    static esp_err_t Command(httpd_req_t* req) {
        if (!instance_) return ESP_FAIL;
        std::string m = Query(req,"m");
        auto* x = instance_->motors_;
        if (m=="forward") x->Forward(35,350);
        else if (m=="backward") x->Backward(35,350);
        else if (m=="left") x->TurnLeft(38,300);
        else if (m=="right") x->TurnRight(38,300);
        else if (m=="spin") x->Spin360(true);
        else if (m=="dance") x->Dance();
        else x->Stop();
        return httpd_resp_sendstr(req,"OK");
    }

    static esp_err_t Settings(httpd_req_t* req) {
        if (!instance_) return ESP_FAIL;
        std::string spin = Query(req,"spin");
        std::string stop = Query(req,"stop");
        if (!spin.empty()) instance_->motors_->SetSpin360Ms(atoi(spin.c_str()));
        if (!stop.empty()) instance_->motors_->SetStopDistanceMm(atoi(stop.c_str()));
        return httpd_resp_sendstr(req,"OK");
    }
};


class RobotAiPrivateV1Board : public WifiBoard {
public:
    RobotAiPrivateV1Board() : boot_button_(BOOT_BUTTON_GPIO) {
        ESP_LOGI(TAG, "ROBOT_PRIVATE_V6_DUAL_BRAIN_20260828");
        InitializeSpi();
        InitializeDisplay();
        InitializeButton();
        lights_.Init();
        tof_.Init();
        motors_.Init(&tof_);
        admin_.Init(&motors_, &tof_);
        device_web_.Init(&motors_, &tof_);
        InitializeTools();
        StartFaceTask();
        GetBacklight()->RestoreBrightness();
    }

    AudioCodec* GetAudioCodec() override {
        static NoAudioCodecSimplex codec(
            AUDIO_INPUT_SAMPLE_RATE,
            AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_SPK_GPIO_BCLK,
            AUDIO_I2S_SPK_GPIO_LRCK,
            AUDIO_I2S_SPK_GPIO_DOUT,
            AUDIO_I2S_MIC_GPIO_SCK,
            AUDIO_I2S_MIC_GPIO_WS,
            AUDIO_I2S_MIC_GPIO_DIN
        );
        return &codec;
    }
    Display* GetDisplay() override { return display_; }
    Led* GetLed() override {
        static SingleLed led(BUILTIN_LED_GPIO);
        return &led;
    }
    Backlight* GetBacklight() override {
        static PwmBacklight b(DISPLAY_BACKLIGHT_PIN,DISPLAY_BACKLIGHT_OUTPUT_INVERT);
        return &b;
    }

private:
    Button boot_button_;
    RobotFaceDisplay* display_=nullptr;
    Tof050c tof_;
    MotorController motors_;
    RobotLights lights_;
    MacBridgeClient mac_;
    RobotAdminUdp admin_;
    RobotDeviceWeb device_web_;
    TaskHandle_t face_task_=nullptr;

    void InitializeSpi(){
        spi_bus_config_t b={};
        b.mosi_io_num=DISPLAY_SPI_MOSI_PIN;
        b.miso_io_num=GPIO_NUM_NC;
        b.sclk_io_num=DISPLAY_SPI_SCK_PIN;
        b.quadwp_io_num=GPIO_NUM_NC;
        b.quadhd_io_num=GPIO_NUM_NC;
        b.max_transfer_sz=DISPLAY_WIDTH*DISPLAY_HEIGHT*sizeof(uint16_t);
        ESP_ERROR_CHECK(spi_bus_initialize(SPI3_HOST,&b,SPI_DMA_CH_AUTO));
    }

    void InitializeDisplay(){
        esp_lcd_panel_io_handle_t io=nullptr;
        esp_lcd_panel_handle_t panel=nullptr;
        esp_lcd_panel_io_spi_config_t i={};
        i.cs_gpio_num=DISPLAY_SPI_CS_PIN;
        i.dc_gpio_num=DISPLAY_DC_PIN;
        i.spi_mode=DISPLAY_SPI_MODE;
        i.pclk_hz=40*1000*1000;
        i.trans_queue_depth=10;
        i.lcd_cmd_bits=8;
        i.lcd_param_bits=8;
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(SPI3_HOST,&i,&io));

        esp_lcd_panel_dev_config_t p={};
        p.reset_gpio_num=DISPLAY_RST_PIN;
        p.rgb_ele_order=LCD_RGB_ELEMENT_ORDER_RGB;
        p.bits_per_pixel=16;
        ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(io,&p,&panel));
        ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
        ESP_ERROR_CHECK(esp_lcd_panel_init(panel));
        ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel,DISPLAY_INVERT_COLOR));
        ESP_ERROR_CHECK(esp_lcd_panel_swap_xy(panel,DISPLAY_SWAP_XY));
        ESP_ERROR_CHECK(esp_lcd_panel_mirror(panel,DISPLAY_MIRROR_X,DISPLAY_MIRROR_Y));
        ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel,true));

        display_=new RobotFaceDisplay(io,panel,DISPLAY_WIDTH,DISPLAY_HEIGHT,
                                     DISPLAY_OFFSET_X,DISPLAY_OFFSET_Y,
                                     DISPLAY_MIRROR_X,DISPLAY_MIRROR_Y,DISPLAY_SWAP_XY);
    }

    void InitializeButton(){
        boot_button_.OnClick([this](){
            auto& app=Application::GetInstance();
            if(app.GetDeviceState()==kDeviceStateStarting){
                EnterWifiConfigMode();
                return;
            }
            app.ToggleChatState();
        });
        boot_button_.OnLongPress([this](){
            motors_.Stop();
            EnterWifiConfigMode();
        });
    }

    static RobotFace ParseFace(const std::string& s){
        if(s=="listen") return RobotFace::Listening;
        if(s=="talk") return RobotFace::Speaking;
        if(s=="think") return RobotFace::Thinking;
        if(s=="tease") return RobotFace::Teasing;
        if(s=="surprise") return RobotFace::Surprise;
        if(s=="angry") return RobotFace::Angry;
        if(s=="music") return RobotFace::Music;
        return RobotFace::Idle;
    }

    void StartFaceTask(){
        xTaskCreate([](void* p){
            auto* self=static_cast<RobotAiPrivateV1Board*>(p);
            int64_t next_blink=esp_timer_get_time()+2600000;
            for(;;){
                switch(Application::GetInstance().GetDeviceState()){
                    case kDeviceStateListening: self->display_->Request(RobotFace::Listening); break;
                    case kDeviceStateSpeaking: self->display_->Request(RobotFace::Speaking); break;
                    case kDeviceStateConnecting:
                    case kDeviceStateActivating: self->display_->Request(RobotFace::Thinking); break;
                    default: self->display_->Request(RobotFace::Idle); break;
                }
                int64_t now=esp_timer_get_time(); bool blink=now>=next_blink;
                if(blink) next_blink=now+(2200+(esp_random()%3000))*1000LL;
                self->display_->Tick(blink);
                vTaskDelay(pdMS_TO_TICKS(blink?90:120));
            }
        },"face_task",4096,this,2,&face_task_);
    }

    void InitializeTools(){
        auto& m=McpServer::GetInstance();

        m.AddTool(
            "self.robot.motion",
            "Điều khiển robot bằng lời nói tiếng Việt. action: forward=tiến, "
            "backward=lùi, left=quay trái, right=quay phải, "
            "spin_left=quay một vòng trái, spin_right=quay một vòng phải, stop=dừng. "
            "Nếu người dùng nói quay 1 vòng/quay một vòng thì dùng spin_right.",
            PropertyList(std::vector<Property>{
                Property("action",kPropertyTypeString),
                Property("speed",kPropertyTypeInteger,20,65),
                Property("duration_ms",kPropertyTypeInteger,80,3200)
            }),
            [this](const PropertyList& p)->ReturnValue{
                std::string a=p["action"].value<std::string>();
                int s=p["speed"].value<int>();
                int ms=p["duration_ms"].value<int>();
                if(a=="forward") motors_.Forward(s,ms);
                else if(a=="backward") motors_.Backward(s,ms);
                else if(a=="left") motors_.TurnLeft(s,ms);
                else if(a=="right") motors_.TurnRight(s,ms);
                else if(a=="spin_left") motors_.Spin360(false);
                else if(a=="spin_right") motors_.Spin360(true);
                else motors_.Stop();
                return true;
            });

        m.AddTool("self.robot.stop","Dừng khẩn cấp hai động cơ.",
                  PropertyList(),[this](const PropertyList&)->ReturnValue{
                      motors_.Stop(); return true;
                  });

        m.AddTool("self.robot.wiggle","Lắc người nhẹ để biểu cảm vui/cà khịa.",
                  PropertyList(),[this](const PropertyList&)->ReturnValue{
                      motors_.Wiggle(); return true;
                  });

        m.AddTool("self.robot.dance","Cho robot nhảy/chuyển động vui ngắn.",
                  PropertyList(),[this](const PropertyList&)->ReturnValue{
                      motors_.Dance(); display_->Manual(RobotFace::Teasing,3200); return true;
                  });

        m.AddTool("self.robot.distance","Đọc khoảng cách TOF050C theo mm.",
                  PropertyList(),[this](const PropertyList&)->ReturnValue{
                      return tof_.DistanceMm();
                  });

        m.AddTool(
            "self.robot.calibrate_spin360",
            "Hiệu chuẩn thời gian quay 360 độ. milliseconds 600..3000; lưu NVS.",
            PropertyList(std::vector<Property>{Property("milliseconds",kPropertyTypeInteger,600,3000)}),
            [this](const PropertyList& p)->ReturnValue{
                motors_.SetSpin360Ms(p["milliseconds"].value<int>());
                return motors_.Spin360Ms();
            });


        m.AddTool(
            "self.robot.settings",
            "Đọc hoặc thay đổi hiệu chuẩn robot. action: status, set_spin360_ms, set_stop_distance_mm.",
            PropertyList(std::vector<Property>{
                Property("action",kPropertyTypeString),
                Property("value",kPropertyTypeInteger,0,4000)
            }),
            [this](const PropertyList& p)->ReturnValue{
                std::string a=p["action"].value<std::string>();
                int v=p["value"].value<int>();
                if(a=="set_spin360_ms") {
                    motors_.SetSpin360Ms(v);
                    return motors_.Spin360Ms();
                }
                if(a=="set_stop_distance_mm") {
                    motors_.SetStopDistanceMm(v);
                    return motors_.StopDistanceMm();
                }
                return std::string("spin360_ms=")+std::to_string(motors_.Spin360Ms())+
                       " stop_mm="+std::to_string(motors_.StopDistanceMm())+
                       " distance_mm="+std::to_string(tof_.DistanceMm());
            });

        m.AddTool(
            "self.robot.face",
            "Biểu cảm: idle, listen, talk, think, tease, surprise, angry, music.",
            PropertyList(std::vector<Property>{Property("mode",kPropertyTypeString)}),
            [this](const PropertyList& p)->ReturnValue{
                display_->Manual(ParseFace(p["mode"].value<std::string>()),2800);
                return true;
            });

        m.AddTool(
            "self.robot.lights",
            "Đèn trang trí: off, left, right, both.",
            PropertyList(std::vector<Property>{Property("mode",kPropertyTypeString)}),
            [this](const PropertyList& p)->ReturnValue{
                auto s=p["mode"].value<std::string>();
                if(s=="left") lights_.Set(true,false);
                else if(s=="right") lights_.Set(false,true);
                else if(s=="both") lights_.Set(true,true);
                else lights_.Set(false,false);
                return true;
            });


        m.AddTool(
            "self.robot.server_profile",
            "Chuyển máy chủ hội thoại. action: status, private, public_xiaozhi. "
            "private dùng máy chủ riêng trên Mac; public_xiaozhi dùng Xiaozhi công cộng và robot sẽ khởi động lại.",
            PropertyList(std::vector<Property>{Property("action",kPropertyTypeString)}),
            [this](const PropertyList& p)->ReturnValue{
                std::string action=p["action"].value<std::string>();
                Settings brain("robot_brain", action!="status");
                std::string current=brain.GetString("server_profile","private");

                if(action=="status"){
                    Settings wifi("wifi",false);
                    std::string ota=wifi.GetString("ota_url","");
                    return std::string("profile=")+current+
                           " ota_override="+(ota.empty() ? std::string("<default-private>") : ota);
                }

                if(action=="private"){
                    Settings wifi("wifi",true);
                    wifi.EraseKey("ota_url");
                    brain.SetString("server_profile","private");
                } else if(action=="public_xiaozhi"){
                    Settings wifi("wifi",true);
                    wifi.SetString("ota_url",ROBOT_PUBLIC_XIAOZHI_OTA_URL);
                    brain.SetString("server_profile","public_xiaozhi");
                } else {
                    return std::string("action_invalid");
                }

                xTaskCreate([](void*){
                    vTaskDelay(pdMS_TO_TICKS(900));
                    esp_restart();
                },"brain_reboot",3072,nullptr,2,nullptr);

                return std::string("switching_to=")+action+" rebooting=true";
            });

        m.AddTool(
            "self.mac.command",
            "Điều khiển Mac mini trong LAN. action: open_chrome, open_safari, "
            "open_youtube, youtube_search, web_search, open_word, word_write, "
            "open_finder, open_app, type_text, volume_up, volume_down, play_pause, "
            "play_music_youtube, radio_vov1, radio_vov2, radio_vov_gt. "
            "Không hỗ trợ xóa file, shell tùy ý, mật khẩu hay thanh toán.",
            PropertyList(std::vector<Property>{
                Property("action",kPropertyTypeString),
                Property("value",kPropertyTypeString)
            }),
            [this](const PropertyList& p)->ReturnValue{
                return mac_.Call(p["action"].value<std::string>(),
                                 p["value"].value<std::string>());
            });
    }
};

DECLARE_BOARD(RobotAiPrivateV1Board);
