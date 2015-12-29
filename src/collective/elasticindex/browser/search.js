
(function($, JSON) {
    // Hang on in there. We have jQuery, 1.4.
    var BATCH_SIZE = 15;
    var ALLOWED_COLON_WORDS = /(title|description|contributors|subject|content)$/i;

    // Lucene special chars: && || ! ( ) { } [ ] ^ \
    // Following regex contains Lucene special chars and punctuation chars (the colon it's treated separately).
    // Chars with a "meaning" in regex syntax have been escaped.
    var DISALLOWED_CHARS = /(&|\||!|\(|\)|\{|\}|\[|\]|\^|\\|;|,|\.|\/|<|>)/g;

    var remove_colons_from_query = function(query) {
        var origin = query.split(':'),
            cleaned = [],
            i, match, len;
        for (i=0, len=origin.length; i <len; i++) {
            match = origin[i].search(ALLOWED_COLON_WORDS);
            if (match > -1) {
                cleaned.push(origin[i].substring(0, match));
                cleaned.push(origin[i].substring(match).toLowerCase());
                cleaned.push(':');
            } else {
                cleaned.push(origin[i]);
            }
        }
        return cleaned.join('');
    };

    var validate_year = function(year) {
        if (year.match(/^\d{4}$/)) {
            return year;
        };
        return null;
    };

    var ElasticSearch = function($form) {
        var search_urls = $form.data('server-urls');
        // List of callbacks during the various search stages.
        var start_query = [],
            empty_results = [],
            results = [];
        // Private variables.
        var previous_query = null;

        var get_url = function() {
            // Return an URL where to post the search query.
            return search_urls[Math.floor(Math.random() * search_urls.length)];
        };

        var build_query = function(original) {
            // Build the search query out of the the collect data.
            var queries = [],
                filters = [],
                query = null,
                sort = {};
            // Sorting options.
            if (original.sort == 'created' || original.sort == 'modified') {
                sort[original.sort] = 'desc';
            } else if (original.sort == 'title') {
                sort = "sortableTitle";
            } else {
                sort = "_score";
            };
            // Search criterias
            if (original.term) {
                queries.push({
                    query_string : {
                        query: remove_colons_from_query(original.term.replace(DISALLOWED_CHARS, ' ')),
                        default_operator: "AND",
                        fields: [
                            "title^3",
                            "contributors^2",
                            "subject^2",
                            "description",
                            "content"
                        ]
                    }
                });
            };
            if (original.contributors) {
                queries.push({match: {contributors: original.contributors}});
            };
            if (original.created) {
                queries.push({range: {created: {from: original.created}}});
            };
            if (original.published_year) {
                if (original.published_before) {
                    queries.push({range: {publishedYear: {lt: original.published_year}}});
                } else if (original.published_after) {
                    queries.push({range: {publishedYear: {gt: original.published_year}}});
                };
            };
            if (original.url) {
                queries.push({prefix: {url: original.url}});
            };
            if (original.subject && original.subject.length) {
                var subjects = [], i;

                for (i=0; i < original.subject.length; i++) {
                    subjects.push({field: {subject: original.subject[i]}});
                };
                if (subjects.length > 1) {
                    if (original.subject_and) {
                        queries.push({bool: {must: subjects}});
                    } else {
                        queries.push({bool: {should: subjects}});
                    };
                } else {
                    queries.push(subjects[0]);
                };
            };

            if (queries.length) {
                if (queries.length > 1) {
                    query = {bool: {must: queries}};
                } else {
                    query = queries[0];
                };

                // Filters
                if (original.meta_type) {
                    filters.push({
                        terms: {
                            metaType: original.meta_type,
                            execution: "or"
                        }
                    });
                };
                if (original.published_year && original.published_in) {
                    filters.push({term: {publishedYear: original.published_year}});
                };
                if (filters.length) {
                    if (filters.length > 1) {
                        query = {
                            filtered: {
                                query: query,
                                filter: {
                                    and: filters
                                }
                            }
                        };
                    } else {
                        query = {
                            filtered: {
                                query: query,
                                filter: filters[0]
                            }
                        };
                    };
                };
            };

            var result = {
                size: BATCH_SIZE,
                sort: [sort],
                highlight: {
                        fields: {
                            title: {number_of_fragments: 0},
                            description: {fragment_size: 150, number_of_fragments: 3}
                        }
                    },
                fields: ['url', 'title', 'description', 'metaType']
            };
            if (query !== null) {
                result['query'] = query;
            };
            return result;
        };

        var do_search = function(query, from) {
            // Post the search query to the server.
            query['from'] = from || 0;
            $.ajax({
                url: get_url(),
                type: 'POST',
                crossDomain: true,
                dataType: 'json',
                success: function(data) {
                    var notifies = data.hits.total ? results : empty_results;
                    for (var i=0, len=notifies.length; i < len; i++) {
                        notifies[i](data.hits, from || 0);
                    }
                },
                error: function () {
                    for (var i=0, len=empty_results.length; i < len; i++) {
                        empty_results[i]();
                    }
                },
                data: JSON.stringify(query)
            });
            return query;
        };

        return {
            subscribe: function(plugin) {
                if (plugin.onempty !== undefined) {
                    empty_results.push(plugin.onempty);
                };
                if (plugin.onresult !== undefined) {
                    results.push(plugin.onresult);
                };
                if (plugin.onstart !== undefined) {
                    start_query.push(plugin.onstart);
                };
            },
            scroll: function(index) {
                if (previous_query !== null) {
                    do_search(previous_query, index);
                };
            },
            search: function(query) {
                for (var i=0, len=start_query.length; i < len; i++) {
                    start_query[i](query);
                };
                previous_query = do_search(build_query(query));
            }
        };
    };

    var SummaryDisplayPlugin = function($summary) {
        var $term = $summary.find('span#esSearchTerm'),
            $location = $summary.find('span#esSearchLocation span');

        return {
            onstart: function(query) {
                $term.text('"' + query.term + '"');
                if (query.url) {
                    $location.text('"' + query.url.replace(/^.*?:\/{2}/,'') + '"');
                    $location.parent().show();
                } else {
                    $location.parent().hide();
                };
            }
        };
    };

    var ResultHeaderDisplayPlugin = function($header) {
        var $loader = $header.find('img'),
            $message = $header.find('span.discreet'),
            $count = $header.find('span.searchResultsCount'),
            initial = true;

        return {
            onstart: function() {
                if (initial) {
                    $header.show();
                    initial = false;
                };
                $loader.show();
                $message.hide();
            },
            onempty: function() {
                $count.text('0');
                $loader.hide();
                $message.show();
            },
            onresult: function(data) {
                $count.text(data.total);
                $loader.hide();
                $message.show();
            }
        };
    };

    var ResultDisplayPlugin = function($result, $empty) {
        var trailing_punctuation_re = /^[;,.\s]*([\S\s]*?)[;,.\s]*$/;

        var trim_punctuation = function(string) {
            var match = [];
            if (typeof string == 'string') {
                match = string.match(trailing_punctuation_re);
            } else {
                for (i=0, len=string.length; i < len; i++) {
                    match.push(string[i].match(trailing_punctuation_re));
                };
            };
            if (match) {
                return match[1];
            }
            return string;
        };

        var truncate_text = function(string) {
            return string.length > 256 ? string.substr(0, 256) + ' &hellip;' : string;
        };

        var get_entry = function(entry) {
            var title = entry.fields.title,
                description = null,
                i;

            if (entry.highlight !== undefined) {
                if (entry.highlight.title !== undefined) {
                    title = entry.highlight.title[0];
                };
                if (entry.highlight.description !== undefined) {
                    description = '&hellip; ';
                    for (i=0; i < entry.highlight.description.length; i++) {
                        description += trim_punctuation(entry.highlight.description[i]) + ' &hellip; ';
                    };
                };
            };
            if (description === null) {
                if (entry.fields.description) {
                    description = trim_punctuation(truncate_text(entry.fields.description));
                } else {
                    description = '';
                };
            };

            mtype = []
            if (typeof entry.fields.metaType == "string") {
                mtype.push(entry.fields.metaType.replace(/^\s+|\s+$/g, '').replace(/\s+/g,'-').toLowerCase());
            } else {
                for (i=0, len=entry.fields.metaType.length; i < len; i++) {
                    mtype.push(entry.fields.metaType[i].replace(/^\s+|\s+$/g, '').replace(/\s+/g,'-').toLowerCase());
                }
            }
            return {
                title: title,
                description: description,
                url: entry.fields.url,
                meta_type: mtype
            };
        };

        return {
            onempty: function() {
                $result.hide();
                $empty.show();
            },
            onresult: function(data) {
                var entry, i, len;

                $empty.hide();
                $result.empty();
                $result.show();
                for (i=0, len=data.hits.length; i < len; i++) {
                    entry = get_entry(data.hits[i]);
                    $result.append(
                        '<dt class="contenttype-'
                            + entry.meta_type + '"><a href="'
                            + entry.url + '">' + entry.title + '</a></dt><dd>'
                            + entry.description + '</dd>'
                    );
                };
            }
        };
    };

    var BatchDisplayPlugin = function($batch, update) {
        var PAGING    = 3,
            NO_LEAP   = 0,
            PRE_LEAP  = 1,
            POST_LEAP = 2,

            $prev = $('span.previous'),
            $next = $('span.next'),

            $prev_a = $('span.previous a'),
            $next_a = $('span.next a'),

            $prev_size = $('span.previous a span span'),
            $next_size = $('span.next a span span'),

            link_to = function (opt) {
                var $item;

                if (opt.current) {
                    $item = $('<span class="esGeneratedBatch current"> ' + opt.page + ' </span>');
                } else {
                    $item = $('<a class="esGeneratedBatch" href=""> ' + opt.page + ' </a>');

                    if (opt.leap) {
                        var $leap = $('<span>&hellip;</span>');
                        if (opt.leap == PRE_LEAP) {
                            $item.prepend($leap);
                        } else {
                            $item.append($leap);
                        }
                    };

                    $item.bind('click', function () {
                        update((opt.page - 1) * BATCH_SIZE);
                        return false;
                    });
                };
                return $item;
            };

        return {
            onempty: function() {
                $batch.hide();
            },
            onresult: function(data, current) {
                $batch.hide();

                if (data.total <= BATCH_SIZE) {
                    return;
                }

                $batch.children('.esGeneratedBatch').remove();

                var page_count = Math.ceil(data.total / BATCH_SIZE);
                var current_page = Math.ceil(current / BATCH_SIZE) + 1;
                var $current = link_to({page : current_page, current: true});

                $current.insertAfter($next);

                for (var i = PAGING; i >= 1; i--) {
                    if (current_page - i <= 1) {
                        continue;
                    }
                    link_to({page : current_page - i}).insertBefore($current);
                };

                for (var i = PAGING; i >= 1; i--) {
                    if (current_page + i >= page_count) {
                        continue;
                    }
                    link_to({page : current_page + i}).insertAfter($current);
                };

                if (current_page > 1) {
                    var first_leap = current_page - PAGING > 2 ? POST_LEAP : NO_LEAP;
                    $prev_size.text(BATCH_SIZE);
                    $prev_a.unbind();
                    $prev_a.bind('click', function () { update(current - BATCH_SIZE); return false });
                    $prev.show();
                    link_to({page: 1, leap: first_leap}).insertAfter($next);
                } else {
                    $prev.hide();
                };

                if (current_page < page_count) {
                    var last_leap = current_page + PAGING < (page_count - 2) ? PRE_LEAP : NO_LEAP;
                    var next_size = Math.min(data.total - (current_page * BATCH_SIZE), BATCH_SIZE);
                    $next_size.text(next_size);
                    $next_a.unbind();
                    $next_a.bind('click', function () { update(current + BATCH_SIZE); return false });
                    $next.show();
                    link_to({page: page_count, leap: last_leap}).appendTo($batch);
                } else {
                    $next.hide();
                };

                $batch.show();
            }
        };
    };

    $(document).ready(function() {
        $('.esSearchForm').each(function() {
            var $form = $(this),

                $resultHeader = $form.find('h1.esResultHeader'),
                $searchResults = $form.find('dl.searchResults'),
                $listingBar = $form.find('div.listingBar'),
                $emptyResults = $form.find('div.emptySearchResults'),
                $summaryBox = $form.find('div#esSearchSummaryBox'),

                $options = $form.find('div.esSearchOptions'),
                search = ElasticSearch($form);

            var $query = $form.find('input.searchPage'),
                $author = $form.find('input#Contribs'),
                $subject = $form.find('select#Subject'),
                $subject_operator = $form.find('input#Subject_and'),
                $since = $form.find('select#created'),
                $published = $form.find('input#Published'),
                $published_before = $form.find('input#Published_before'),
                $published_in = $form.find('input#Published_in'),
                $published_after = $form.find('input#Published_after'),
                $current = $form.find('input#CurrentFolderOnly'),
                $button = $form.find('input[type=submit]'),
                $sort = $form.find('select#sort_on'),
                $meta_types = $form.find('input[id^="portal_type_"]'),
                options = $options.hasClass('expanded'),
                previous = null,
                timeout = null;

            var scroll_search = function(index) {
                if (timeout !== null) {
                    clearTimeout(timeout);
                    timeout = null;
                };
                search.scroll(index);
            };

            var schedule_search = function(force) {
                if (timeout !== null) {
                    clearTimeout(timeout);
                };

                var search_term = $query.val();

                timeout = setTimeout(function () {
                    var query = {term: search_term},
                        meta_types = [];

                    if ($current.is(":checked")) {
                        query['url'] = $current.val();
                    };

                    if (options) {
                        query['contributors'] = $author.val();
                        query['subject'] = $subject.val();
                        query['subject_and'] = $subject_operator.is(":checked");
                        query['created'] = $since.val();
                        query['sort'] = $sort.val();
                        query['published_year'] = validate_year($published.val());
                        query['published_before'] = $published_before.is(":checked");
                        query['published_in'] = $published_in.is(":checked");
                        query['published_after'] = $published_after.is(":checked");

                        $meta_types.each(function () {
                            var $field = $(this);
                            if ($field.is(':checked')) {
                                meta_types.push($field.val());
                            };
                        });
                        if (meta_types.length) {
                            query['meta_type'] = meta_types;
                        };
                    };

                    if (force || query.term != previous && !options) {
                        search.search(query);
                        previous = query.term;
                    };
                    timeout = null;
                }, 300);
            };

            search.subscribe(SummaryDisplayPlugin($summaryBox));
            search.subscribe(ResultHeaderDisplayPlugin($resultHeader));
            search.subscribe(ResultDisplayPlugin($searchResults, $emptyResults));
            search.subscribe(BatchDisplayPlugin($listingBar, scroll_search));

            $form.find('p.esSearchOptions a').bind('click', function (event) {
                options = !options;
                $options.slideToggle();
                event.preventDefault();
            });

            $button.bind('click', function(event) {
                schedule_search(true);
                event.preventDefault();
            });
            $options.delegate('input,select', 'change', schedule_search);
            $query.bind('change', schedule_search);
            $query.bind('keyup', schedule_search);
            if ($query.val() || options) {
                if (options) {
                    $options.show();
                    $options.removeClass('expanded');
                };
                schedule_search(true);
            };
        });
    });

})(jQuery, JSON);
