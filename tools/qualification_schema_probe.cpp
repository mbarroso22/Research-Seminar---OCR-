// Offline b6500 ordered-schema converter only. No llama/model/server linkage.
#include "json-schema-to-grammar.h"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <sstream>
#include <vector>

std::string string_join(const std::vector<std::string> &values, const std::string &sep) {
    std::ostringstream out;
    for (size_t i=0;i<values.size();++i) { if(i)out<<sep; out<<values[i]; }
    return out.str();
}
std::string string_repeat(const std::string &s, size_t count) {
    std::string out; for(size_t i=0;i<count;++i)out+=s; return out;
}
std::vector<std::string> string_split(const std::string &s, const std::string &sep) {
    std::vector<std::string> out; size_t begin=0,end=s.find(sep);
    while(end!=std::string::npos) {out.push_back(s.substr(begin,end-begin));begin=end+sep.size();end=s.find(sep,begin);}
    out.push_back(s.substr(begin));return out;
}
int main(int argc,char **argv) {
    try {
        if(argc!=2)return 2;
        std::ifstream in(argv[1],std::ios::binary);
        if(!in)return 2;
        const auto schema=nlohmann::ordered_json::parse(in);
        std::cout<<json_schema_to_grammar(schema,true);
        return 0;
    } catch(const std::exception &e) {std::cerr<<e.what();return 2;}
}
