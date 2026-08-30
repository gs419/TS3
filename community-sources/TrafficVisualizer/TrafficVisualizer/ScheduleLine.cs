using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace TrafficVisualizer
{
    public class ScheduleLine
    {
        public string? OperatorColor { get; set; }
        public string? AirlineCallsign { get; set; }
        public string? FlightNumber { get; set; }
        public string? AirplaneType { get; set; }
        public string? FromICAO { get; set; }
        public string? ToICAO { get; set; }
        public string? ApproachTime { get; set; }
        public string? DepartureTime { get; set; }
        public string? ApproachAltitude { get; set; }
        public string? Special { get; set; }
        public string? Registration { get; set; }

        public bool IsCargo => Special != null && Special.ToLower().Contains("cargo");

        public static ScheduleLine? Parse(string line)
        {
            var m = new Regex("(?:^|,)(?=[^\"]|(\")?)\"?((?(1)[^\"]*|[^,\"]*))\"?(?=,|$)").Matches(line);
            if (m.Count > 9) 
                return new ScheduleLine
                {
                    OperatorColor = m[0].Groups[2].Value.Trim(),
                    AirlineCallsign = m[1].Groups[2].Value.Trim(),
                    FlightNumber = m[2].Groups[2].Value.Trim(),
                    AirplaneType = m[3].Groups[2].Value.Trim(),
                    FromICAO = m[4].Groups[2].Value.Trim(),
                    ToICAO = m[5].Groups[2].Value.Trim(),
                    ApproachTime = m[6].Groups[2].Value.Trim(),
                    DepartureTime = m[7].Groups[2].Value.Trim(),
                    ApproachAltitude = m[8].Groups[2].Value.Trim(),
                    Special = m[9].Groups[2].Value.Trim()
                };
            else return null;
        }
    }
}
