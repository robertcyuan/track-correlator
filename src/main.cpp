#include <nlohmann/json.hpp>

#include <cstddef>
#include <iostream>
#include <string>

// Placeholder: answers every report with a track of its own. Replace with your correlator.
int main()
{
    std::string line;
    for(std::size_t index = 0; std::getline(std::cin, line); ++index)
    {
        const nlohmann::json report = nlohmann::json::parse(line);
        const nlohmann::json answer{
            { "report", index },
            { "track", "T" + std::to_string(index) },
            { "at", report.at("arr") },
        };
        std::cout << answer << std::endl;
    }
}
