Frequently Asked Questions
==========================

Some frequently asked questions, and potential answers.

The labels are laid out badly, how do I fix it?
-----------------------------------------------

Bad layouts are usually due to simply having too many (and occasionally too few) labels.
The best thing to do is to try the get fewer (or occasionally more) clusters labelled. Some
other options include adjusting some of the label layout options (see the Label Placement Options)
making the label size smaller (see Size Options), or adjusting the ``label_base_radius``
as a last resort.

The location indicators point to empty space, why?
--------------------------------------------------

The location indicators point to the centroid of the cluster. For non-compact clusters that
might not be any point in the cluster. The simplest workaround for this is to set ``use_medoids``
to true, which will use medoids instead of centroids. Alternatively you can compute or set
your own "locations" for the clusters and pass those directly to ``render_plot`` instead.

I want to have XYZ appear in the plot, how do I do that?
--------------------------------------------------------

DataMapPlot provides the basics for a static labelled data map plot. Obviously there is a lot
more that could be done, but it would go well beyond the scope of this library. Fortunately
DataMapPlot will return a matplotlib Figure and Axes, which you can then apply whatever extra
matplotlib commands you wish to, to add extra plot elements, or otherwise alter things
(at your own risk). If you feel you have a pretty common adjustment, consider submitting a PR
to the library so we can make it available to everyone.

The title is cut off when I save the plot, how do I fix that?
-------------------------------------------------------------

For complex reasons not worth getting into it is necessary to put ``bbox_inches="tight"`` in 
the call to ``savefig`` to ensure that the title and subtitle don't end up getting clipped.

Something isn't working with my interactive plot, help?
-------------------------------------------------------

Interactive plots are a bit more complex than static plots, and there are a lot of things that
can go wrong. The first thing to do is to check the javascript console in your browser for any 
error messages. The next step is to save the html file and open that in an editor and see if
there are any obvious issues.