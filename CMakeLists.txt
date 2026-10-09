cmake_minimum_required(VERSION 3.24)
project(correlator CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

include(FetchContent)
FetchContent_Declare(json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
    URL_HASH SHA256=d6c65aca6b1ed68e7a182f4757257b107ae403032760ed6ef121c9d55e81757d)
FetchContent_Declare(Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG v3.7.1)
FetchContent_MakeAvailable(json Catch2)

add_executable(correlator src/main.cpp)
target_link_libraries(correlator PRIVATE nlohmann_json::nlohmann_json)

enable_testing()
add_executable(correlator_tests tests/correlator_tests.cpp)
target_link_libraries(correlator_tests PRIVATE Catch2::Catch2WithMain)
add_test(NAME correlator_tests COMMAND correlator_tests)
