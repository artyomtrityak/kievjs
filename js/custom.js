//<![CDATA[ 
$(window).load(function(){
/*$("body").tooltip({
selector: "a[rel=tooltip]",
placement: "top"
});
$("body").popover({
selector: ".popover-test",
placement: "right"
});
$('.myCarousel').carousel({
  interval: 2000
})
*/
$.router(/\w+/, function(section) {
    $("section.content").hide();
    $("#" + section).parent().show();
});

if (!window.location.hash) {
    $('section.content').hide();
    $('#about').parent().show();
}

/*$('#sponsor .row').masonry({
  itemSelector: 'div.span6'
});
*/


});//]]>  
