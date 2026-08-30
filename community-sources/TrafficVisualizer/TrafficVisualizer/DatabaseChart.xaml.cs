using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;

namespace TrafficVisualizer
{
    /// <summary>
    /// Interaction logic for ScheduleChart.xaml
    /// </summary>
    public partial class DatabaseChart : UserControl
    {


        public Database Database
        {
            get { return (Database)GetValue(DatabaseProperty); }
            set { SetValue(DatabaseProperty, value); }
        }

        // Using a DependencyProperty as the backing store for Database.  This enables animation, styling, binding, etc...
        public static readonly DependencyProperty DatabaseProperty =
            DependencyProperty.Register("Database", typeof(Database), typeof(DatabaseChart), new PropertyMetadata(null));



        public bool SeparateCargo
        {
            get { return (bool)GetValue(SeparateCargoProperty); }
            set { SetValue(SeparateCargoProperty, value); }
        }

        // Using a DependencyProperty as the backing store for SeparateCargo.  This enables animation, styling, binding, etc...
        public static readonly DependencyProperty SeparateCargoProperty =
            DependencyProperty.Register("SeparateCargo", typeof(bool), typeof(DatabaseChart), new PropertyMetadata(false));


        public DatabaseChart()
        {
            InitializeComponent();
        }

        public void UpdateChart()
        {
            double height = Y.ActualHeight;
            if (height == double.NaN) return;
            if (Database==null) return;
            int max = 0;
            for (int i = 0; i < 24; i++) {
                int v = Database.Distribution[i * 6] + Database.Distribution[i * 6 + 1] + Database.Distribution[i * 6 + 2] + Database.Distribution[i * 6 + 3] + Database.Distribution[i * 6 + 4] + Database.Distribution[i * 6 + 5];
                max=Math.Max(max, v);
            }
            if (max == 0) return;
            double scale = height / max;
            int spacing = max > 200 ? 50 : 20;
            int k = 0;
            while (k < G.Children.Count) {
                var c= G.Children[k] as FrameworkElement;
                if (c?.Tag as string == "*")
                    G.Children.RemoveAt(k);
                else k++;
            }
            int y = spacing;
            while (y < max) {
                Rectangle r=new Rectangle() { HorizontalAlignment= HorizontalAlignment.Stretch, Height=1, Fill= Brushes.Gray, VerticalAlignment= VerticalAlignment.Bottom, Margin=new Thickness(0,0,0,y*scale), Tag="*"};
                Grid.SetRow(r,1);
                Grid.SetColumn(r,1);
                Grid.SetColumnSpan(r,24);
                G.Children.Add(r);
                TextBlock t= new TextBlock() { TextAlignment= TextAlignment.Right,Text=y.ToString(),VerticalAlignment=VerticalAlignment.Bottom,Margin=new Thickness(0,0,8,y*scale-6),Height=16, Tag="*" };
                Grid.SetRow(t,1);
                G.Children.Add(t);
                y += spacing;
            }
            tMax.Text=(max%spacing >(spacing/2))?max.ToString():"";
            // build bar stacks
            for (int h = 0; h < 24; h++) {
                int l = 0;
                // arrivals
                int ht = Database.Distribution[h * 6];
                if (ht>0) {
                    Rectangle r = new Rectangle { HorizontalAlignment = HorizontalAlignment.Stretch, Height = scale * ht, VerticalAlignment = VerticalAlignment.Bottom, Fill = Brushes.Orange, Stroke=Brushes.Black, Tag = "*", ToolTip=$"{ht} arrivals" };
                    Grid.SetColumn(r, h + 1);
                    Grid.SetRow(r, 1);
                    G.Children.Add(r);
                    if (ht*scale>20) {
                        TextBlock t = new TextBlock { Text = ht.ToString(), TextAlignment = TextAlignment.Center, VerticalAlignment = VerticalAlignment.Bottom, Tag = "*", Margin=new Thickness(0,0,0,(l+ht/2.0)*scale-7) };
                        Grid.SetColumn(t, h+1);
                        Grid.SetRow(t, 1);
                        G.Children.Add(t);
                    }
                    l += ht;
                }
                // cargo arrivals
                ht = Database.Distribution[h * 6+4];
                if (ht > 0) {
                    Rectangle r = new Rectangle { HorizontalAlignment = HorizontalAlignment.Stretch, Height = scale * ht, VerticalAlignment = VerticalAlignment.Bottom, Fill = Brushes.Tomato, Margin = new Thickness(0, 0, 0, l * scale), Stroke = Brushes.Black, Tag = "*", ToolTip = $"{ht} cargo arrivals" };
                    Grid.SetColumn(r, h + 1);
                    Grid.SetRow(r, 1);
                    G.Children.Add(r);
                    if (ht * scale > 20) {
                        TextBlock t = new TextBlock { Text = ht.ToString(), TextAlignment = TextAlignment.Center, VerticalAlignment = VerticalAlignment.Bottom, Tag = "*", Margin = new Thickness(0, 0, 0, (l + ht / 2.0) * scale - 7) };
                        Grid.SetColumn(t, h + 1);
                        Grid.SetRow(t, 1);
                        G.Children.Add(t);
                    }
                    l += ht;
                }
                // departures
                ht = Database.Distribution[h * 6+1];
                if (ht > 0) {
                    Rectangle r = new Rectangle { HorizontalAlignment = HorizontalAlignment.Stretch, Height = scale * ht, VerticalAlignment = VerticalAlignment.Bottom, Fill = Brushes.SkyBlue,Margin=new Thickness(0,0,0,l*scale), Stroke = Brushes.Black, Tag = "*", ToolTip = $"{ht} departures" };
                    Grid.SetColumn(r, h + 1);
                    Grid.SetRow(r, 1);
                    G.Children.Add(r);
                    if (ht * scale > 20) {
                        TextBlock t = new TextBlock { Text = ht.ToString(), TextAlignment = TextAlignment.Center, VerticalAlignment = VerticalAlignment.Bottom, Tag = "*", Margin = new Thickness(0, 0, 0, (l + ht / 2.0) * scale - 7) };
                        Grid.SetColumn(t, h + 1);
                        Grid.SetRow(t, 1);
                        G.Children.Add(t);
                    }
                    l += ht;
                }
                // cargo departures
                ht = Database.Distribution[h * 6 + 5];
                if (ht > 0) {
                    Rectangle r = new Rectangle { HorizontalAlignment = HorizontalAlignment.Stretch, Height = scale * ht, VerticalAlignment = VerticalAlignment.Bottom, Fill = Brushes.CadetBlue, Margin = new Thickness(0, 0, 0, l * scale), Stroke = Brushes.Black, Tag = "*", ToolTip = $"{ht} cargo departures" };
                    Grid.SetColumn(r, h + 1);
                    Grid.SetRow(r, 1);
                    G.Children.Add(r);
                    if (ht * scale > 20) {
                        TextBlock t = new TextBlock { Text = ht.ToString(), TextAlignment = TextAlignment.Center, VerticalAlignment = VerticalAlignment.Bottom, Tag = "*", Margin = new Thickness(0, 0, 0, (l + ht / 2.0) * scale - 7) };
                        Grid.SetColumn(t, h + 1);
                        Grid.SetRow(t, 1);
                        G.Children.Add(t);
                    }
                    l += ht;
                }
                // ga arrivals
                ht = Database.Distribution[h * 6 + 2];
                if (ht > 0) {
                    Rectangle r = new Rectangle { HorizontalAlignment = HorizontalAlignment.Stretch, Height = scale * ht, VerticalAlignment = VerticalAlignment.Bottom, Fill = Brushes.Coral, Margin = new Thickness(0, 0, 0, l * scale), Stroke = Brushes.Black, Tag = "*", ToolTip = $"{ht} GA arrivals" };
                    Grid.SetColumn(r, h + 1);
                    Grid.SetRow(r, 1);
                    G.Children.Add(r);
                    if (ht * scale > 20) {
                        TextBlock t = new TextBlock { Text = ht.ToString(), TextAlignment = TextAlignment.Center, VerticalAlignment = VerticalAlignment.Bottom, Tag = "*", Margin = new Thickness(0, 0, 0, (l + ht / 2.0) * scale - 7) };
                        Grid.SetColumn(t, h + 1);
                        Grid.SetRow(t, 1);
                        G.Children.Add(t);
                    }
                    l += ht;
                }
                // ga departures
                ht = Database.Distribution[h * 6 + 3];
                if (ht > 0) {
                    Rectangle r = new Rectangle { HorizontalAlignment = HorizontalAlignment.Stretch, Height = scale * ht, VerticalAlignment = VerticalAlignment.Bottom, Fill = Brushes.LightGreen, Margin = new Thickness(0, 0, 0, l * scale), Stroke = Brushes.Black, Tag = "*", ToolTip = $"{ht} GA departures" };
                    Grid.SetColumn(r, h + 1);
                    Grid.SetRow(r, 1);
                    G.Children.Add(r);
                    if (ht * scale > 20) {
                        TextBlock t = new TextBlock { Text = ht.ToString(), TextAlignment = TextAlignment.Center, VerticalAlignment = VerticalAlignment.Bottom, Tag = "*", Margin = new Thickness(0, 0, 0, (l + ht / 2.0) * scale - 7) };
                        Grid.SetColumn(t, h + 1);
                        Grid.SetRow(t, 1);
                        G.Children.Add(t);
                    }
                    l += ht;
                }
            }
        }
        private void Canvas_DataContextChanged(object sender, DependencyPropertyChangedEventArgs e)
        {
            UpdateChart();
        }

        private void Canvas_SizeChanged(object sender, SizeChangedEventArgs e)
        {
            UpdateChart();

        }
    }
}
