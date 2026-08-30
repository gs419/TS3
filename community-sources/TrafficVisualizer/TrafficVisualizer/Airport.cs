using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace TrafficVisualizer
{
    class Airport
    {
        public string? ICAO { get; set; }
        public List<Database> Databases { get; set; } = new();
    }
}
