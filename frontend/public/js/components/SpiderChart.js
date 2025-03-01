export class SpiderChart {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.options = {
            width: options.width || 250,
            height: options.height || 250,
            margin: options.margin || 50,
            levels: options.levels || 5,
            maxValue: options.maxValue || 1,
            labelFactor: options.labelFactor || 1.2,
            wrapWidth: options.wrapWidth || 100,
            opacityArea: options.opacityArea || 0.35,
            dotRadius: options.dotRadius || 4,
            opacityCircles: options.opacityCircles || 0.1,
            strokeWidth: options.strokeWidth || 2,
            color: options.color || d3.scaleOrdinal(d3.schemeCategory10)
        };

        this.data = options.data || [
            {
                className: "default",
                axes: [
                    { axis: "Proximity", value: 0.2 },
                    { axis: "Density", value: 0.2 },
                    { axis: "Entropy", value: 0.2 },
                    { axis: "Accessibility", value: 0.2 }
                ]
            }
        ];

        this.initChart();
    }

    initChart() {
        this.cfg = this.options;
        this.allAxis = this.data[0].axes.map(i => i.axis);
        this.total = this.allAxis.length;
        this.radius = Math.min(this.cfg.width / 2, this.cfg.height / 2);

        // Create the container
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Container with id '${this.containerId}' not found`);
            return;
        }

        // Create the SVG container
        container.innerHTML = '';
        this.svg = d3.select(`#${this.containerId}`).append("svg")
            .attr("width", this.cfg.width + this.cfg.margin)
            .attr("height", this.cfg.height + this.cfg.margin)
            .attr("class", "spider-chart");

        // Create a group for the chart
        this.g = this.svg.append("g")
            .attr("transform", `translate(${this.cfg.width / 2 + this.cfg.margin / 2}, ${this.cfg.height / 2 + this.cfg.margin / 2})`);

        // Draw the circular levels
        this.drawLevels();

        // Draw the axes
        this.drawAxes();

        // Draw the data
        this.drawData();
    }

    drawLevels() {
        for (let j = 0; j < this.cfg.levels; j++) {
            const levelFactor = this.radius * ((j + 1) / this.cfg.levels);

            // Draw level circles
            this.g.selectAll(".levels").data([1])
                .enter().append("circle")
                .attr("class", "gridCircle")
                .attr("r", levelFactor)
                .style("fill", "#CDCDCD")
                .style("stroke", "#CDCDCD")
                .style("fill-opacity", this.cfg.opacityCircles)
                .style("filter", "url(#glow)");

            // Draw level labels
            this.g.selectAll(".levels").data([1])
                .enter().append("text")
                .attr("class", "levelLabel")
                .attr("x", 5)
                .attr("y", -levelFactor)
                .attr("dy", "0.35em")
                .style("font-size", "10px")
                .style("fill", "#737373")
                .text(Math.round((j + 1) * this.cfg.maxValue / this.cfg.levels * 100) / 100);
        }
    }

    drawAxes() {
        const axis = this.g.selectAll(".axis")
            .data(this.allAxis)
            .enter().append("g")
            .attr("class", "axis");

        // Draw axis lines
        axis.append("line")
            .attr("x1", 0)
            .attr("y1", 0)
            .attr("x2", (d, i) => this.radius * Math.cos(this.angleSlice(i) - Math.PI / 2))
            .attr("y2", (d, i) => this.radius * Math.sin(this.angleSlice(i) - Math.PI / 2))
            .attr("class", "line")
            .style("stroke", "white")
            .style("stroke-width", "2px");

        // Draw axis labels
        axis.append("text")
            .attr("class", "legend")
            .style("font-size", "11px")
            .attr("text-anchor", "middle")
            .attr("dy", "0.35em")
            .attr("x", (d, i) => this.radius * this.cfg.labelFactor * Math.cos(this.angleSlice(i) - Math.PI / 2))
            .attr("y", (d, i) => this.radius * this.cfg.labelFactor * Math.sin(this.angleSlice(i) - Math.PI / 2))
            .text(d => d)
            .call(this.wrap, this.cfg.wrapWidth);
    }

    drawData() {
        const radarLine = d3.lineRadial()
            .curve(d3.curveLinearClosed)
            .radius(d => d * this.radius)
            .angle((d, i) => this.angleSlice(i));

        // Create a wrapper for the blobs
        const blobWrapper = this.g.selectAll(".radarWrapper")
            .data(this.data)
            .enter().append("g")
            .attr("class", "radarWrapper");

        // Append the backgrounds
        blobWrapper.append("path")
            .attr("class", "radarArea")
            .attr("d", d => radarLine(d.axes.map(p => p.value / this.cfg.maxValue)))
            .style("fill", (d, i) => typeof this.cfg.color === "function" ? this.cfg.color(i) : this.cfg.color)
            .style("fill-opacity", this.cfg.opacityArea)
            .on("mouseover", function() {
                d3.select(this).transition().duration(200).style("fill-opacity", 0.7);
            })
            .on("mouseout", function() {
                d3.select(this).transition().duration(200).style("fill-opacity", 0.35);
            });

        // Create the outlines
        blobWrapper.append("path")
            .attr("class", "radarStroke")
            .attr("d", d => radarLine(d.axes.map(p => p.value / this.cfg.maxValue)))
            .style("stroke-width", this.cfg.strokeWidth + "px")
            .style("stroke", (d, i) => typeof this.cfg.color === "function" ? this.cfg.color(i) : this.cfg.color)
            .style("fill", "none")
            .style("filter", "url(#glow)");

        // Append the circles
        blobWrapper.selectAll(".radarCircle")
            .data(d => d.axes)
            .enter().append("circle")
            .attr("class", "radarCircle")
            .attr("r", this.cfg.dotRadius)
            .attr("cx", (d, i) => this.radius * (d.value / this.cfg.maxValue) * Math.cos(this.angleSlice(i) - Math.PI / 2))
            .attr("cy", (d, i) => this.radius * (d.value / this.cfg.maxValue) * Math.sin(this.angleSlice(i) - Math.PI / 2))
            .style("fill", (d, i, j) => typeof this.cfg.color === "function" ? this.cfg.color(j) : this.cfg.color)
            .style("fill-opacity", 0.8);

        // Create invisible circles for tooltips
        const blobCircleWrapper = this.g.selectAll(".radarCircleWrapper")
            .data(this.data)
            .enter().append("g")
            .attr("class", "radarCircleWrapper");

        blobCircleWrapper.selectAll(".radarInvisibleCircle")
            .data(d => d.axes)
            .enter().append("circle")
            .attr("class", "radarInvisibleCircle")
            .attr("r", this.cfg.dotRadius * 1.5)
            .attr("cx", (d, i) => this.radius * (d.value / this.cfg.maxValue) * Math.cos(this.angleSlice(i) - Math.PI / 2))
            .attr("cy", (d, i) => this.radius * (d.value / this.cfg.maxValue) * Math.sin(this.angleSlice(i) - Math.PI / 2))
            .style("fill", "none")
            .style("pointer-events", "all")
            .on("mouseover", (event, d) => {
                const newX = parseFloat(d3.select(event.target).attr('cx')) - 10;
                const newY = parseFloat(d3.select(event.target).attr('cy')) - 10;

                this.tooltip
                    .attr('x', newX)
                    .attr('y', newY)
                    .text(`${d.axis}: ${Math.round(d.value * 100)}%`)
                    .transition().duration(200)
                    .style('opacity', 1);
            })
            .on("mouseout", () => {
                this.tooltip.transition().duration(200)
                    .style("opacity", 0);
            });

        // Create tooltip
        this.tooltip = this.g.append("text")
            .attr("class", "tooltip")
            .style("opacity", 0)
            .style("font-size", "12px");

        // Add Filter for the glow effect
        const filter = this.svg.append('defs').append('filter').attr('id', 'glow');
        filter.append('feGaussianBlur').attr('stdDeviation', '2.5').attr('result', 'coloredBlur');
        const feMerge = filter.append('feMerge');
        feMerge.append('feMergeNode').attr('in', 'coloredBlur');
        feMerge.append('feMergeNode').attr('in', 'SourceGraphic');
    }

    updateData(newData) {
        this.data = newData;
        this.svg.remove();
        this.initChart();
    }

    angleSlice(i) {
        return i * (Math.PI * 2 / this.total);
    }

    wrap(text, width) {
        text.each(function() {
            const text = d3.select(this);
            const words = text.text().split(/\s+/).reverse();
            let word;
            let line = [];
            let lineNumber = 0;
            const lineHeight = 1.4; // ems
            const y = text.attr("y");
            const x = text.attr("x");
            const dy = parseFloat(text.attr("dy"));
            let tspan = text.text(null).append("tspan").attr("x", x).attr("y", y).attr("dy", dy + "em");

            while (word = words.pop()) {
                line.push(word);
                tspan.text(line.join(" "));
                if (tspan.node().getComputedTextLength() > width) {
                    line.pop();
                    tspan.text(line.join(" "));
                    line = [word];
                    tspan = text.append("tspan").attr("x", x).attr("y", y).attr("dy", ++lineNumber * lineHeight + dy + "em").text(word);
                }
            }
        });
    }
}