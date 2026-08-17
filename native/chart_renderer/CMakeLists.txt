cmake_minimum_required(VERSION 3.21)

project(SagittariusNativeChart LANGUAGES CXX)

set(QT_SKIP_AUTO_QML_PLUGIN_INCLUSION ON)
find_package(Qt6 6.11 REQUIRED COMPONENTS Qml Quick)

qt_standard_project_setup(REQUIRES 6.11)

qt_add_qml_module(sagittarius_native_chart
    URI Sagittarius.NativeChart
    VERSION 1.0
    SHARED
    OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/qml/Sagittarius/NativeChart"
    SOURCES
        native_chart_item.cpp
        native_chart_item.h
        snapshot_abi.h
)

set(native_qml_module_dir "${CMAKE_BINARY_DIR}/qml/Sagittarius/NativeChart")
set_target_properties(
    sagittarius_native_chart
    sagittarius_native_chartplugin
    PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${native_qml_module_dir}"
        LIBRARY_OUTPUT_DIRECTORY "${native_qml_module_dir}"
        BUILD_RPATH "$ORIGIN"
)
foreach(configuration Debug Release RelWithDebInfo)
    string(TOUPPER "${configuration}" configuration_upper)
    set_target_properties(
        sagittarius_native_chart
        sagittarius_native_chartplugin
        PROPERTIES
            "RUNTIME_OUTPUT_DIRECTORY_${configuration_upper}" "${native_qml_module_dir}"
            "LIBRARY_OUTPUT_DIRECTORY_${configuration_upper}" "${native_qml_module_dir}"
    )
endforeach()

target_compile_features(sagittarius_native_chart PRIVATE cxx_std_20)
target_link_libraries(sagittarius_native_chart PRIVATE Qt6::Qml Qt6::Quick)

if(MSVC)
    target_compile_options(sagittarius_native_chart PRIVATE /W4 /permissive-)
else()
    target_compile_options(sagittarius_native_chart PRIVATE -Wall -Wextra -Wpedantic)
endif()

configure_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/native-chart-runtime.json.in"
    "${CMAKE_BINARY_DIR}/qml/native-chart-runtime.json"
    @ONLY
)

install(
    TARGETS sagittarius_native_chart sagittarius_native_chartplugin
    RUNTIME DESTINATION qml/Sagittarius/NativeChart
    LIBRARY DESTINATION qml/Sagittarius/NativeChart
)
install(
    FILES
        "${native_qml_module_dir}/qmldir"
        "${native_qml_module_dir}/sagittarius_native_chart.qmltypes"
    DESTINATION qml/Sagittarius/NativeChart
)
install(
    FILES "${CMAKE_BINARY_DIR}/qml/native-chart-runtime.json"
    DESTINATION qml
)
