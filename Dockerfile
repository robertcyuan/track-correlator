# Reference build environment: the submission must build and pass its tests here, unmodified.
FROM gcc:14

RUN apt-get update \
 && apt-get install -y --no-install-recommends cmake ninja-build git curl zip unzip tar pkg-config \
 && rm -rf /var/lib/apt/lists/* \
 && git clone --depth 1 https://github.com/microsoft/vcpkg /opt/vcpkg \
 && /opt/vcpkg/bootstrap-vcpkg.sh -disableMetrics

ENV VCPKG_ROOT=/opt/vcpkg
WORKDIR /src
COPY . .
RUN cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake \
 && cmake --build build \
 && ctest --test-dir build --output-on-failure

ENTRYPOINT ["/src/build/correlator"]
