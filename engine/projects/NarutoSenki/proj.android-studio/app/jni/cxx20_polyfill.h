// C++20 helpers used by the game, provided for C++17 builds (std::format would clash with fmt::format).
#pragma once
#ifdef __cplusplus
#include <algorithm>
#include <vector>
#include <list>
#include <string>
namespace std {
template <class T, class A, class U>
inline typename vector<T, A>::size_type erase(vector<T, A>& c, const U& v) {
    auto it = remove(c.begin(), c.end(), v); auto r = c.end() - it; c.erase(it, c.end()); return r; }
template <class T, class A, class P>
inline typename vector<T, A>::size_type erase_if(vector<T, A>& c, P p) {
    auto it = remove_if(c.begin(), c.end(), p); auto r = c.end() - it; c.erase(it, c.end()); return r; }
template <class T, class A, class U>
inline typename list<T, A>::size_type erase(list<T, A>& c, const U& v) { auto n = c.size(); c.remove(v); return n - c.size(); }
template <class T, class A, class P>
inline typename list<T, A>::size_type erase_if(list<T, A>& c, P p) { auto n = c.size(); c.remove_if(p); return n - c.size(); }
}
#endif
