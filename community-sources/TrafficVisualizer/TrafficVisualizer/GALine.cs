using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace TrafficVisualizer
{
    public class GALine
    {
        public string? Callsign { get; set; }
        public string? AirplaneType { get; set; }
        public string? FromICAO { get; set; }
        public string? ToICAO { get; set; }
        public string? ArriveTime { get; set; }
        public string? DepartureTime { get; set; }
        public static GALine? Parse(string line)
        {
            var m = new Regex("(?:^|,)(?=[^\"]|(\")?)\"?((?(1)[^\"]*|[^,\"]*))\"?(?=,|$)").Matches(line);
            if (m.Count > 6)
                return new GALine
                {
                    Callsign = m[0].Groups[2].Value.Trim(),
                    AirplaneType = m[2].Groups[2].Value.Trim(),
                    FromICAO = m[3].Groups[2].Value.Trim(),
                    ToICAO = m[4].Groups[2].Value.Trim(),
                    ArriveTime = m[5].Groups[2].Value.Trim(),
                    DepartureTime = m[6].Groups[2].Value.Trim()
                };
            else return null;
        }

    }
}
