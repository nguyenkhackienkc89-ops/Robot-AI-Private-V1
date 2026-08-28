idf_component_register(
    SRCS "robot_ai_private_v1.cc"
    INCLUDE_DIRS "."
    REQUIRES esp_http_client esp_driver_gpio
)
